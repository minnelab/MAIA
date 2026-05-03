#!/bin/bash -e

pid=$(pgrep -xn plasmashell) && export DBUS_SESSION_BUS_ADDRESS="$(grep -ao -m1 -P '(?<=DBUS_SESSION_BUS_ADDRESS=).*?\0' /proc/"$pid"/environ)"

qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
    var allDesktops = desktops();                                                                                   
    for (i=0;i<allDesktops.length;i++) 
    {
        d = allDesktops[i];
        d.wallpaperPlugin = "org.kde.image";
        d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
        d.writeConfig("Image", "file:///etc/bitmap.png")
    }
'