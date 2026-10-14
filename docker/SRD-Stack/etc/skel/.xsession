#!/bin/sh
pulseaudio -D --enable-memfd=True
exec xfce4-session
