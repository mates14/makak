import numpy as np
from scipy.optimize import minimize_scalar

def apply_dark_correction(image, calibration, temperature):
    """Apply dark frame correction using the calibration file."""
    A, B, C = calibration[:, :, 0], calibration[:, :, 1], calibration[:, :, 2]
    dark_current = A * np.power(B, temperature) + C
    return image - dark_current

def calculate_image_noise(image):
    """Calculate the sum of differences between neighboring pixels."""
    return np.sum(np.abs(np.diff(image, axis=1)))

def optimize_temperature(image, calibration, initial_temp, temp_range=10):
    """Find the optimal temperature by minimizing image noise."""
    def objective(temp):
        corrected = apply_dark_correction(image, calibration, temp)
        return calculate_image_noise(corrected)
    
    result = minimize_scalar(
        objective,
        method='brent',
        bracket=(initial_temp - temp_range/2, initial_temp + temp_range/2)
    )
    
    if not result.success:
        print(f"Warning: Temperature optimization did not converge. Using initial temperature.")
        return initial_temp
    
    if abs(result.x - initial_temp) > temp_range:
        print(f"Warning: Optimized temperature ({result.x:.2f}) is far from initial temperature ({initial_temp:.2f}). Using initial temperature.")
        return initial_temp
    
    return result.x

def smart_dark(image, calibration_path, initial_temp=20.0):
    """
    Apply smart dark correction to an image.
    
    Parameters:
    - image: numpy array of the image data (should be float64)
    - calibration_path: path to the .npy file containing the dark calibration data
    - initial_temp: initial temperature guess (default 20.0°C)
    
    Returns:
    - corrected_image: numpy array of the corrected image data
    - optimal_temp: the optimized temperature used for correction
    """
    calibration = np.load(calibration_path)
    
    optimal_temp = optimize_temperature(image, calibration, initial_temp)
    
    corrected_image = apply_dark_correction(image, calibration, optimal_temp)
    
    return corrected_image, optimal_temp

# Example usage:
# from smart_dark import smart_dark
# corrected_data, optimal_temp = smart_dark(img_fits[0].data.astype(np.float64), "dark_characterization2.npy")
