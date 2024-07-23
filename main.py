# requires pillow img ext.
# pip install --upgrade Pillow

import os
import struct
import json
from PIL import Image, ImageFont, ImageDraw

MAX_BYTES_TO_CONSUME = -300_000 # A negative value is simply ignored.
MAX_SCAN_LINES =          -10   # A negative value is simply ignored.
MAX_SERIES_TO_EXTRACT =   924   # A negative value extracts everything!

font = ImageFont.truetype("SQ3n001.ttf", 25)
fSeries = totalConsumed = 0
extractTextures = True # export the game images to img/
exportPal = False # export palette image to pal/
extractSound = False # export audio files to sound/
debug = False # log additional debug info

# Counters
cels_extracted = 0
warn_cels_skipped = 0

def extractAudio(file):
	fnum = 0
	os.makedirs("sound/"+file, exist_ok = True)
	with open("vol/"+file, "rb") as f:
		while (byte := f.read(1)):
			if byte == b'\x52' and f.read(1) == b'\x49' and f.read(1) == b'\x46' and f.read(1) == b'\x46':
				size = struct.unpack('<i', f.read(4))[0]
				if debug:
					print("Found RIFF starting at: ", f.tell()-4)
					print("wav size: ", size)
				f.seek(-8, 1)
				wav = f.read(size+8)
				s = "sound/" + file + "/" + str(fnum) + ".wav"
				fnum=fnum+1
				nf = open(s, 'bw+')
				nf.write(wav)
				nf.close()
				print("saved " + s)

def logUnknown(f):
	t = ['<h', '<H', '<b', '<B']
	for x in t:
		f.seek(-8, 1)
		u = []
		m = i = b = 0
		s = ""
		match x:
			case '<h':
				m = 4
				b = 2
				s = "4 s16"
			case '<H':
				m = 4
				b = 2
				s = "4 u16"
			case '<b':
				m = 8
				b = 1
				s = "8 s8"
			case '<B':
				m = 8
				b = 1
				s = "8 u8"
		while (i < m):
			u.append(struct.unpack(str(x), f.read(b))[0])
			i += 1
		match x:
			case '<h' | '<H':
				print("  0x310: as " + s + ": " + str(u[0])+", "+str(u[1])+", "+str(u[2])+", "+str(u[3]))
			case '<b' | '<B':
				print("  0x310: as " + s + ":  " + str(u[0])+", "+str(u[1])+", "+str(u[2])+", "+str(u[3])+", "+str(u[4])+", "+str(u[5])+", "+str(u[6])+", "+str(u[7]))

def exportPalImg(series, pal):
	i = x = y = 0
	im = Image.new('RGB', (16, 16), (255, 255, 255))
	draw = ImageDraw.Draw(im)
	while (i<256):
		p = i * 3
		r = pal[p]
		g = pal[p + 1]
		b = pal[p + 2]
		draw.rectangle((x, y, x+1, y+1), fill=(r, g, b))
		x += 1
		if (x > 16):
			x = 0
			y += 1
		i += 1
	os.makedirs("pal", exist_ok = True)
	s = f"pal/pal_{series}.png"
	im.save(s, quality=100)

def consumeSingleByte(f):
	global totalConsumed
	if MAX_BYTES_TO_CONSUME > 0 and totalConsumed >= MAX_BYTES_TO_CONSUME:
		raise Exception("max bytes consumed")
	result = struct.unpack('<B', f.read(1))[0]
	totalConsumed +=1
	return result

def consumeNBytes(f, howMany):
	global totalConsumed
	totalConsumed += howMany
	return f.read(howMany)

def unconsumeBytes(f, howMany):
	howMany *= -1
	global totalConsumed
	f.seek(howMany, 1)
	totalConsumed -= howMany

def deRLE(f, pal, draw, width, height):
	y = 0
	streamPadding = 0
	while (y < height):
		if MAX_SCAN_LINES > 0 and y >= MAX_SCAN_LINES:
			# Only evaluate when negative.
			return
		
		x = 0
		while (x < width):
			haveRun = False
			haveLiteralSeq = False
			haveSingleRunNonTransparent = False
			try:
				singleByte = consumeSingleByte(f)
			except Exception as e:
				if str(e) == "max bytes consumed":
					return
				streamPadding +=1
				singleByte = 0

			# Conjecture 1: these may be power of 2 control values
			# 	Haven't yet seen a meaningful case for 0x4 yet.
			# Conjecture 2: almost no difference between 0x01 and 0x08
			#	Perhaps 0x08 allows for a WORD size runLen rather than limited to BYTE.
			if singleByte == 0x01:
				# Basic case: Single Color Run, often used for transparency.
				# Next byte: <runLen>
				# Next byte: <colorIdx>
				runLen = consumeSingleByte(f)
				colorIdx = consumeSingleByte(f)
				haveRun = True
			elif singleByte == 0x02:
				# Literal case: a sequence of differing N literal bytes.
				literalLen = consumeSingleByte(f)
				zeroDelimiter = consumeSingleByte(f)
				haveLiteralSeq = True
			elif singleByte == 0x08:
				# Single Color Run: NON-transparency
				runLen = consumeSingleByte(f)
				zeroDelimiter = consumeSingleByte(f)
				haveSingleRunNonTransparent = True

			if haveRun:
				p = colorIdx * 3
				r = pal[p] 
				g = pal[p + 1]
				b = pal[p + 2]
				draw.rectangle((x, y, x+runLen, y+1), fill=(r, g, b))
				if debug:
					print(f"Run: x={x}, y={y}, runLen={runLen} (0x{runLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
				# Increment x by runLen.
				x += runLen
			elif haveLiteralSeq:
				for i in range(literalLen):
					colorIdx = consumeSingleByte(f)
					p = colorIdx * 3
					r = pal[p]
					g = pal[p + 1] 
					b = pal[p + 2]
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					if debug:
						print(f"Literal: x={x}, y={y}, litLen={literalLen} (0x{literalLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
					x +=1
			elif haveSingleRunNonTransparent:
				colorIdx = consumeSingleByte(f)
				p = colorIdx * 3
				r = pal[p]
				g = pal[p + 1] 
				b = pal[p + 2]
				for i in range(runLen):
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					x +=1
			else:
				# At least for Peter, these else values must be skipped!
				# NOTE: I have to see if this holds true for other textures.
				pass
				# hotPink = (0xfe, 0x24, 0xb6)
				# draw.rectangle((x, y, x+1, y+1), fill=hotPink)
				# print(f"else: x={x}, y={y}, byte=0x{singleByte:x}, color=HOT_PINK")
				#x += 1
		y += 1
	if debug:
		print("WARN: stream padded with: " + str(streamPadding) + " bytes!!")

def processTexture(f, series):
	textureOffset = f.tell()
	
	i = 0
	pal = []
	while ( i < 768):
		c = consumeSingleByte(f)
		pal.append(c)
		i += 1
	if exportPal and not os.path.exists(f"pal/{series}_Pal.png"):
		exportPalImg(series, pal)

	# This unknown sometimes contains texture's frame count.
	unknown = consumeNBytes(f, 4)
	if debug:
		logUnknown(f)

	# The possible values of the first byte in unknown are: 1, 10 & 17 
	NUM_IMAGES = 0
	SKIP_BYTES = 0
	if (unknown[0] == 1):
		# "0x01"
		NUM_IMAGES = unknown[2] # could NUM_IMAGES acutally be a WORD?
		SKIP_BYTES = 8
	elif (unknown[0] == 10):
		# "0x0A" These seem to only be small character portraits
		next2Bytes = consumeNBytes(f, 2)
		NUM_IMAGES = next2Bytes[0] # is this correct?
		SKIP_BYTES = 6
	elif (unknown[0] == 17):
		# "0x11"  large character portraits
		next2Bytes = consumeNBytes(f, 2)
		NUM_IMAGES = next2Bytes[0] # missing animation frames? Investigate
		SKIP_BYTES = 6
	
	# Handle each image
	# TODO: extract NUM_IMAGES from somewhere above.
	# Observation: subsprites in a series can have different width/height vals.
	#	so to make it easy, I'm just generating single files and not atlases.
	# Observation: For Peter test file, I confirmed that it spits out 2 duplicate images
	# so it's really just 10 unique animation sprites. Verified with md5 check.
	i = 0
	for i in range(NUM_IMAGES):
		width = struct.unpack('<H', consumeNBytes(f, 2))[0]
		height = struct.unpack('<H', consumeNBytes(f, 2))[0]
		if width > 640 or height > 480:
			print(f"WARN: width: {width} or height: {height} exceeds expected values. Skipping series: {series}, cel: {i}")
			global warn_cels_skipped
			warn_cels_skipped +=1
			continue
		
		im = Image.new('RGB', (width, height), (255, 255, 255))
		draw = ImageDraw.Draw(im)
		
		consumeNBytes(f, SKIP_BYTES)
		if debug:
			print('arbitrary consumed: ' + str(totalConsumed))

		deRLE(f, pal, draw, width, height)

		os.makedirs("img", exist_ok = True)
		s = f"img/sprite_{series}_{i}.png"
		im.save(s, quality=100)
		print(f"saved {s} from origin offset: 0x{textureOffset:x}")
		global cels_extracted
		cels_extracted +=1

def processTextureList(texList, vol):
	global fSeries
	with open(vol, 'rb') as f:
		for i, offset in enumerate(texList):
			# Caveat: the last texture offset gets stuck.
			if i == 925:
				print("Stopping at 925th texture offset cause it gets stuck...")
				return
			f.seek(offset, 0)
			processTexture(f, fSeries)
			fSeries +=1

def findTextures(vol):
	print("Scanning textures, please wait...")
	texList = []
	with open(vol, "rb") as f:
		while (byte := consumeNBytes(f, 1)):
			if (byte == b'\x74' and consumeNBytes(f, 1) == b'\x65' and consumeNBytes(f, 1) == b'\x78' and
				consumeNBytes(f, 1) == b'\x20' and consumeNBytes(f, 1) == b'\x30' and consumeNBytes(f, 1) == b'\x30' and 
				consumeNBytes(f, 1) == b'\x30' and consumeNBytes(f, 1) == b'\x31'):
				texList.append(f.tell())
	print(f"Identified {len(texList)} individual textures!")
	return texList

def buildOrLoadOffsetTable():
	CACHE_FOLDER = "cache"
	CACHE_FILE = "tex_offset_tbl.json"
	os.makedirs(CACHE_FOLDER, exist_ok = True)
	if not os.path.exists(f"{CACHE_FOLDER}/{CACHE_FILE}"):
		offTbl = findTextures(f"vol/RESOURCE.VOL")
		with open(f'{CACHE_FOLDER}/{CACHE_FILE}', 'w') as jf:
			json.dump(offTbl, jf, indent=4)
			return offTbl
	else:
		with open(f'{CACHE_FOLDER}/{CACHE_FILE}', 'r') as jf:
			return json.load(jf)
		
def extractBin(offTbl, n):
	# quick and dirty
	with open("vol/RESOURCE.VOL", 'rb') as f:
		f.seek(offTbl[n]-8)
		b = f.read(offTbl[n+1]-offTbl[n])
		s = "test_textures/" + str(n) + ".bin"
		nf = open(s, 'bw+')
		nf.write(b)
		nf.close()

def run():
	# scanResource("test_textures/peter_texture_isolated.bin")
	if os.path.exists(f"vol/RESOURCE.VOL"):
		if extractTextures:
			offTbl = buildOrLoadOffsetTable()
			#extractBin(offTbl, 906)
			processTextureList(offTbl, f"vol/RESOURCE.VOL")
			print(f"Summary - Total Series: {fSeries}, Cels Extracted: {cels_extracted}, Cels Skipped: {warn_cels_skipped}")
		if extractSound:
			extractAudio("RESOURCE.VOL")
	else:
		print("ERROR: 'vol/RESOURCE.VOL' missing")
	if os.path.exists(f"vol/audio.vol") and extractSound:
		extractAudio("audio.vol")
	else:
		if extractSound:
			print("WARN: 'vol/audio.vol' missing")

if __name__ == "__main__":
	run()

