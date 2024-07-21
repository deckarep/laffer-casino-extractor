# Extract wav files from Larry's Casino audio.vol
# Sound effects can also be dumped from resources.vol
# jokes are 71.wav - 183.wav
#
# command to convert wav to mp3:
# for f in *.wav; do ffmpeg -i "$f" "${f%.wav}.mp3"; done

import struct
fnum = 0

with open("audio.vol", "rb") as f:
	while (byte := f.read(1)):
		if byte == b'\x52' and f.read(1) == b'\x49' and f.read(1) == b'\x46' and f.read(1) == b'\x46':
			print("Found RIFF starting at: ", f.tell()-4)
			size = struct.unpack('<i', f.read(4))[0]
			print("wav size: ", size)
			f.seek(-8, 1)
			wav = f.read(size+8)
			s = str(fnum) + ".wav"
			fnum=fnum+1
			nf = open(s, 'bw+')
			nf.write(wav)
			nf.close()