#!/bin/bash
# plot last 24h of makak output

pushd /home/mates/makak-reloaded/plot

#now=`date +%s`

# get the last file
file=`ls /home/mates/makak-reloaded/nght/mr*.dat | sort | tail -n1`
dfile=`ls /home/mates/makak-reloaded/nght/mr*d.dat | sort | tail -n1`

echo $file 

if [ $1 ]; then
 file=$1
 dfile=${file%.dat}d.dat
fi

echo $file 

now=`sort $file | tail -n1 | awk '{printf("%ld\n", ($2-2440587.5)*86400);}'`
now1=`date -d@$[now-43200] +%Y%m%d`
now2=`date -d@$[now-43200] +%Y-%m-%d`

echo $now $now2

eval `ssh -i /home/mates/makak-reloaded/bin/rsa mates@lascaux.asu.cas.cz rts2-state --UT -N -d $now2 2>/dev/null | awk -v d=86400 '/night/{print "tmnight="$1%d-d;} /dawn/{print "tmdawn="$1%d;} /morning/{print "tmmorning="$1%d;} /evening/{print "tmevening="$1%d-d;} /dusk/{print "tmdusk="$1%d-d;}'`
ssh -i /home/mates/makak-reloaded/bin/rsa mates@lascaux.asu.cas.cz rts2-state --UT -d $now2 2>/dev/null | awk -v n1=$now -v n2=$now2 '/morning/ {print n1,n2,$0; }' #| awk -v d=86400 '/night/{print "tmnight="$1%d-d;} /dawn/{print "tmdawn="$1%d;} /morning/{print "tmmorning="$1%d;} /evening/{print "tmevening="$1%d-d;} /dusk/{print "tmdusk="$1%d-d;}'

#title=`echo $file | sed 's/.dat//' | sed 's/-/ /'`

#rts2-state --UT -N -d $now2 | awk -v d=86400 '/night/{print "tmnight="$1%d-d;} /dawn/{print "tmdawn="$1%d;} /morning/{print "tmmorning="$1%d;} /evening/{print "tmevening="$1%d-d;} /dusk/{print "tmdusk="$1%d-d;}'
#CURTEMP=`awk '$2*1.0>0 || $2*1.0<0' $file |tail -n10 |awk ' {a+=$2;b+=1;} END {print 1.00*a/b;}'`
# noise->ph/s/arcsec^2 
# 1 pixel = 56.68" => 3212.7 arcsec2
# noise ~150 ale nemam gain, assume 2.5, 
# (150*2.5)**2 / 3212.7 / 10s exp = 4.38 fot/s/arcsec^2 = 1.75ADU/s/arcsec^2 -> zeropoint = 18.5 (v ADU) -> 17.9, ale plave v tom vlastni sum detektoru


echo gnuplot

gnuplot <<END
#set y2tics
set grid

h=3600.
d=86400.0

# dark noise of the camera (in ADU, fitted on darks):
g=2.00 # kinda true for g1-2000
A=460.0
B=1.2
N=60.0
D(temp) = 1/g*sqrt(g*A*B**temp+N*N*g*g)

# get the CCD intrinsic noise as a function of temperature
fit D(x) "$dfile" u 3:(\$2<150?\$2:NaN) via A

set xtics # ( "16" -8, "18" -6, "20" -4, "22" -2,  0, 2, 4, 6, 8)
set xrange [$tmnight/h:$tmdawn/h]
set ytics nomirror
#set y2tics ()
#do for [i=0:25] { j=int(10*10**((i/4.)-int(i/4.))+0.5)* 10**int(i/4.0); set y2tics add (sprintf("%.0f",j) j); }
#set y2tics (1,1.8,3,5.6,10,18,30,56,100,180,300,560,1000,1800,3000,5600,10000,18000,30000,56000) nomirror
set title "$title"

Z=19.4
s=56.9403 # arcsec/pixel
#g=7.8 # camera gain
#n=(int($now/86400.0+0.5))*86400.0
#print n
#t(x)=(x-n)/h #+12.0
ts(x)=((x+d/2)/d-int((x+d/2)/d)-0.5)*24
t(x)=(x-int(x)-0.5)*24

set terminal png size 1280,1280 large font helvetica 24
set output "makak.png"

dz=0.15
dl=0.3
#g = 2.5

Nplot=4
set multiplot
set origin 0,1.0/Nplot
set size 1.0,3.0/Nplot

set yrange [] reverse

unset xlabel

set x2tics ( sprintf("%.0f:%02.0f",24+int($tmnight/h),60+($tmnight-(h*int($tmnight/h)))/60) $tmnight/h, sprintf("%.0f:%02.0f",int($tmdawn/h),($tmdawn-(h*int($tmdawn/h)))/60) $tmdawn/h )

# barvy: lt rgb "#dda4a4" lt rgb "#dd3333" lt rgb "#a4dda4" lt rgb "#33dd33" lt rgb "#3333dd" 
plot "$file" u (t(\$2)):(\$9<dz?\$8+7.5:NaN) pt 7 ps 0.7 lt rgb "#dd3333" t "Zeropoint/1s",\
 "$file" u (t(\$2)):(\$9<dl?\$10+13.19:NaN) pt 7 ps 0.7 lt rgb "#33dd33" t "Mag limit/1h",\
 "$file" u (t(\$2)):(19.4-2.5*log10((\$14*\$14*g*g-(g*D(\$15))**2)/g/3212.7)) pt 7 ps 0.7 lt rgb "#3333dd" t "sky (mag/arcsec2)"

unset x2tics
set origin 0,0
set size 2.0/Nplot,1.0/Nplot
set yrange [] noreverse
plot "$file" u (t(\$2)):15 pt 7 ps 0.7 lt 1 t "ccdtemp", \\
        "$dfile" u (ts(\$1)):3 pt 7 ps 0.7 lt 2 t "ccdtemp (dark)"

set origin 2.0/Nplot,0
set size 2.0/Nplot,1.0/Nplot
set xrange [*:*] noreverse
set yrange [*:*] noreverse
set xtics auto
set ytics auto

plot "$dfile" u 3:(\$2<150?\$2:NaN) pt 7 t "sigma(T)", D(x)
 

END

dest=`basename mr$now1.png`

echo mv makak.png $dest
mv makak.png $dest

rsync $dest lascaux.asu.cas.cz:/home/mates/public_html/makak/mrpng/

popd
