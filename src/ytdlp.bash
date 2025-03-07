#!/bin/bash

cwd=$PWD

cd $1

counter=1

while IFS= read -r line; do
    yt-dlp -i -f "bv*[ext=mp4]" -N 10 -o "$counter.%(ext)s" $line
    counter=$counter + 1
done < playlists.txt

cd $cwd

# yt-dlp -i -f "bv*[ext=mp4]" -N 10 -o "$counter
