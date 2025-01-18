#!/usr/bin/env python3

import os
import sys
import subprocess
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
import astropy.table as at
from astropy.io import ascii
from shutil import copyfile,move
from pathlib import Path
from datetime import datetime
import tempfile
from smart_dark import smart_dark  # Assuming this is your existing module

def get_sigma(data):
    ndiff = np.zeros(len(data), dtype=np.float64)
    i, j = 0, 0
    while i < len(data) - 1:
        diff = abs(np.float32(data[i]) - np.float32(data[i+1]))
        ndiff[j] = np.nanmedian(diff)
        if not np.isnan(ndiff[j]):
            j += 1
        i += 1
    return np.nanmedian(ndiff)

def solve_field(image_path):
    """Run astrometry.net's solve-field command"""
    cmd = [
        'solve-field',
        '-pT',  # No plots, resort to tweak
        '-u', 'app',  # Image scale units in arcsec/pixel
        '-L', '50',  # Lower bound of image scale
        '-H', '60',  # Upper bound of image scale
        '-l', '30',  # Lower bound of number of stars
        '--overwrite',
        image_path
    ]
    subprocess.run(cmd, check=True)

def process_image(fits_path, model_path="/home/mates/makak-reloaded/model.mod"):
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Open the original FITS file
            img_fits = fits.open(fits_path)
            hdr = img_fits[0].header
            
            # Check if this is a dark frame
            if hdr['slitposx'] < 0.5:
                return process_dark_frame(img_fits, fits_path)

            # Process light frame
            return process_light_frame(img_fits, fits_path, temp_dir, model_path)

        except (IsADirectoryError, OSError) as e:
            print(f"Error processing {fits_path}: {str(e)}")
            return False

def process_dark_frame(img_fits, fits_path):
    """Process dark frame and update necessary files"""
    hdr = img_fits[0].header
    # dark_file = os.path.expanduser('~/tmp2/dark.fits')
    
    try:
        # Calculate dark signature
        dark_data = img_fits[0].data.astype(np.float64)
        test_data, corr_temp = smart_dark(
            dark_data,
            "/home/mates/makak-reloaded/makak-dark-response.npy",
            initial_temp=hdr['CCD_TEMP']
        )
        darksig = get_sigma(test_data)
    except Exception as e:
        print(f"Error calculating dark signature: {str(e)}")
        darksig = 0

    # Write to mr-dark-YYYYMMDD.dat
    c_time = hdr['CTIME']
    datum = datetime.utcfromtimestamp(c_time - 43200)
    datestr = datum.strftime("%Y%m%d")
    
    with open(f'/home/mates/makak-reloaded/nght/mr{datestr}d.dat', 'a+') as fin_data_zero:
        fin_data_zero.write(f"{hdr['CTIME'] + hdr['USEC']/1e6:.6f} {darksig:.3f} {corr_temp:.3f}\n")

    # Copy and update dark file
    # copyfile(fits_path, dark_file)
    # subprocess.run(['fitsheader', '-w', f'darksig={darksig:.3f}', dark_file])
    print(f"Got darksig={darksig:.3f}")
    return True

def process_light_frame(img_fits, fits_path, temp_dir, model_path):
    """Process light frame including astrometry and photometry"""
    hdr = img_fits[0].header
    
    # Calculate date string for the night
    c_time = hdr['CTIME']
    datum = datetime.utcfromtimestamp(c_time - 43200)
    datestr = datum.strftime("%Y%m%d")
    
    # Create paths for temporary files
    base_name = Path(fits_path).stem
    light_file = os.path.join(temp_dir, f"{base_name}d.fits")
    
    # Process the image data
    light_data, corr_temp = smart_dark(
        img_fits[0].data.astype(np.float64),
        "/home/mates/makak-reloaded/makak-dark-response.npy",
        initial_temp=img_fits[0].header['CCD_TEMP']
    )
    
    # Write calibrated image
    cal_hdr = fits.PrimaryHDU(data=light_data, header=hdr)
    bgnoise = get_sigma(cal_hdr.data)
    cal_hdr.writeto(light_file, overwrite=True)
    img_fits.close()

    # Crop image (equivalent to imcopy in shell script)
    with fits.open(light_file) as hdul:
        data = hdul[0].data[19:1218, 215:1414]  # Adjust indices as needed
        header = hdul[0].header
        fits.writeto(light_file.replace('.fits', 'c.fits'), data, header, overwrite=True)

    # Run astrometry
    try:
        solve_field(light_file.replace('.fits', 'c.fits'))
    except subprocess.CalledProcessError:
        print("Astrometry failed")
        return False

    # Run photometry pipeline
    new_file = light_file.replace('.fits', 'c.new')
    if not os.path.exists(new_file):
        return False

    # Rename and process with dophot3
    nf = new_file.replace('.new', 'n.fits')
    os.rename(new_file, nf)
    
    # Update FITS header
    fits.setval(nf, 'BGSIGMA', value=bgnoise)
    fits.setval(nf, 'CCD_NAME', value='makak2')
    fits.setval(nf, 'CCD_TEMP', value=corr_temp)
    
    # Run photometry steps
    pyrt_path = "/home/mates/pyrt/main"
    # subprocess.run([f"{pyrt_path}/cat2det.py", nf])
    subprocess.run([
        f"{pyrt_path}/dophot3.py", "-k", "-l8", "-i5",
        "-U", ".p4,.r4,RC,RO,RS", "-M", model_path,
        nf, "-e1.5", "-C", "makak", "-azS2"
    ])
    
    # Process ECSV file
    ecsv_file = f"{os.path.splitext(nf)[0]}.ecsv"
    subprocess.run([
        f"{pyrt_path}/dophot3.py", "-k", "-l8", "-i3",
        "-U", ".p4,.r4,RC,RO,RS", "-M", model_path,
        ecsv_file, "-s", "-azS2", "-C", "makak" #, "-p"
    ]) #, stdout=open(f"mr{datestr}.out", 'a'))

    # Generate python-based residuals plot
    output_base = os.path.splitext(nf)[0]
    output_filename = f"{output_base}-phot.png"

    # Move the generated plot to the appropriate directory
#    plot_dir = "/home/mates/makak-reloaded/png/f"
#    os.makedirs(plot_dir, exist_ok=True)
#    final_plot_path = os.path.join(plot_dir, os.path.basename(output_filename))

    # If the plot exists, move it to final location
#    if os.path.exists(output_filename):
#        os.rename(output_filename, final_plot_path)

    # Process dophot output
    with open("dophot.dat") as f, open(f"/home/mates/makak-reloaded/nght/mr{datestr}.dat", 'a') as out:
        lines = f.readlines()
        if lines:  # if file is not empty
            out.write(lines[-1])  # write the last line

    # Move ECSV file to final location
    ecsv_dir = f"/home/mates/makak-reloaded/ecsv/{datestr}"
    os.makedirs(ecsv_dir, exist_ok=True)
    move(ecsv_file, f"{ecsv_dir}/{os.path.basename(ecsv_file)}")

    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: makak.py <fits_file>")
        sys.exit(1)
    
    success = process_image(sys.argv[1])
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
