# requires pillow img ext.
# pip install --upgrade Pillow

import argparse
import os
import struct
import json
import pdb
from PIL import Image, ImageFont, ImageDraw

MAX_BYTES_TO_CONSUME = -300_000 # A negative value is simply ignored.
MAX_SCAN_LINES =          -10   # A negative value is simply ignored.
MAX_SERIES_TO_EXTRACT =   924   # A negative value extracts everything!

userArgs = None
font = ImageFont.truetype("SQ3n001.ttf", 25)
fSeries = totalConsumed = 0
extractTextures = True # export the game images to img/
exportPal = False # export palette image to pal/
extractSound = False # export audio files to sound/
debug = False # log additional debug info
hack_offsets = None
# belived to be BGs or compatible with doBackgroundRLE():
bgNums  = [0, 1, 3, 14, 15, 17, 72, 73, 76, 81, 83, 91, 116, 117, 118,
		   119, 120, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 148,
		   149, 150, 152, 153, 258, 277, 282, 287, 289, 296,305, 316, 324,
		   325, 333, 334, 339, 343, 344, 352, 361, 370, 379, 380, 386, 394, 395,
		   396, 402, 412, 414, 418, 419, 428, 435, 442, 474, 484, 490,
		   499, 501, 502, 513, 520, 527, 535, 536, 537, 539, 540, 550, 553, 576,
		   580, 582, 583, 584, 626, 765, 783, 785, 794, 802,
		   811, 812, 821, 829, 834, 835, 845, 853, 861, 871, 872, 880, 884,
		   888, 889, 891, 897, 921]

# Counters
cels_extracted = 0
warn_cels_skipped = 0

def print_alignments(n):
	alignments = [2, 4, 8, 16, 32]
	results = []
	for alignment in alignments:
		if n % alignment == 0:
			results.append(f"✅ {alignment}")
	if len(results) == 0:
		results.append("(NO ALIGNMENT)")
	print(f"Number: {n}, " + ", ".join(results))

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

def doRLE(f, pal, draw, width, height):
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

def doBackgroundRLE(f, pal, draw, width, height):
	y = 0
	streamPadding = 0
	while (y < height):
		if MAX_SCAN_LINES > 0 and y >= MAX_SCAN_LINES:
			# Only evaluate when negative.
			return
		
		# diagnostic line, use line = y for all lines
		line = 269

		wth = consumeNBytes(f, 2)	
		#print("consuming this removes bad pixel at start of each line:")
		#print(wth)

		x = 0
		while (x < width):
			haveLiteralSeq = False
			haveSingleRunNonTransparent = False
			try:
				singleByte = consumeSingleByte(f)
			except Exception as e:
				if str(e) == "max bytes consumed":
					return
				streamPadding +=1
				singleByte = 0
			
			# is 0x04 better? is 0x10?
			if singleByte == 0x02:
				literalLen = consumeSingleByte(f)
				zeroDelimiter = consumeSingleByte(f)
				haveLiteralSeq = True
			elif singleByte == 0x08: # or singleByte == 0x10:
				runLen = consumeSingleByte(f)
				zeroDelimiter = consumeSingleByte(f)
				haveSingleRunNonTransparent = True

			if haveLiteralSeq:
				for i in range(literalLen):
					colorIdx = consumeSingleByte(f)
					p = colorIdx * 3
					r = pal[p]
					g = pal[p + 1] 
					b = pal[p + 2]
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					if (y == line):
						draw.rectangle((x, y, x + 1, y+1), fill=(0, 0, 255))
					x +=1
			elif haveSingleRunNonTransparent:
				colorIdx = consumeSingleByte(f)
				p = colorIdx * 3
				r = pal[p]
				g = pal[p + 1] 
				b = pal[p + 2]
				for i in range(runLen):
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					if (y == line):
						draw.rectangle((x, y, x + 1, y+1), fill=(0, 255, 0))
					x +=1
			else:
				if (zeroDelimiter == 0
					#or zeroDelimiter == 4 # why 4? It improves background 73
					or zeroDelimiter == 8 # debateable if better or worse
					or zeroDelimiter == 10): 
					# checked up to 15
					# test 24, 16, 58, 33, 41, 49, 57, 66, 74, 78, 79, 90, 94, 99, 107
					pass
				else:
					p = singleByte * 3
					r = pal[p]
					g = pal[p + 1] 
					b = pal[p + 2]
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					if (y == line):
						if (zeroDelimiter == 1):
							draw.rectangle((x, y, x + 1, y+1), fill=(255,0,0))
						else:
							draw.rectangle((x, y, x + 1, y+1), fill=(255,255,0))
					x +=1
		y += 1

def processTexture(f, series):
	textureOffset = f.tell()
	
	# Filter by single series.
	if userArgs.series and len(userArgs.series) > 0:
		if series not in userArgs.series:
			return

	# Hacked offset table.
	offsets = series_offsets(series)

	# Palette
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
		# "0x0A" small character portraits
		next2Bytes = consumeNBytes(f, 2)
		NUM_IMAGES = offsets.get("total_cels", 56) if offsets else 56
		SKIP_BYTES = 6
	elif (unknown[0] == 17):
		# "0x11" large character portraits
		next2Bytes = consumeNBytes(f, 2)
		NUM_IMAGES = offsets.get("total_cels", 56) if offsets else 56
		SKIP_BYTES = 6
	
	# Handle each image
	# TODO: extract NUM_IMAGES from somewhere above.
	# Observation: subsprites in a series can have different width/height vals.
	#	so to make it easy, I'm just generating single files and not atlases.
	# Observation: For Peter test file, I confirmed that it spits out 2 duplicate images
	# so it's really just 10 unique animation sprites. Verified with md5 check.
	i = 0
	width = height = 0
	for i in range(NUM_IMAGES):
		celOffset = f.tell()
		width = struct.unpack('<H', consumeNBytes(f, 2))[0]
		height = struct.unpack('<H', consumeNBytes(f, 2))[0]
		if width > 640 or height > 480:
			print(f"WARN: width: {width} or height: {height} exceeds expected values. Skipping series: {series}, cel: {i}")
			global warn_cels_skipped
			warn_cels_skipped +=1
			continue
		
		im = Image.new('RGB', (width, height), (255, 255, 255))
		draw = ImageDraw.Draw(im)
		
		s = consumeNBytes(f, SKIP_BYTES)
		if debug:
			print('arbitrary consumed: ' + str(totalConsumed))

		# debug info
		print("UNKNOWN: ")
		print(unknown)
		print("SKIP_BYTES: ")
		print(s)
		s = consumeNBytes(f, SKIP_BYTES)
		print("NEXT_BYTES: ")
		print(s)
		unconsumeBytes(f, SKIP_BYTES)
		
		if (fSeries in bgNums): # work from list because this is wrong: (unknown[0] == 1 and unknown[2] == 1):
			print("Texture number: ")
			print(fSeries)
			doBackgroundRLE(f, pal, draw, width, height)
		else:
			doRLE(f, pal, draw, width, height)

		os.makedirs("img", exist_ok = True)
		s = f"img/sprite_{series}_{i}.png"
		im.save(s, quality=100)
		print(f"saved {s} from orig_offset: {textureOffset}, cel_offset: {celOffset}")
		global cels_extracted
		cels_extracted +=1

		# The large portrats 17 (0x11) have some unusual padding that Doomlazer figured out.
		# See file: offsets/hack_offsets.json
		if offsets:
			consumerOf2Bytes = offsets.get('consumerOf2Bytes')
			consumerOf4Bytes = offsets.get('consumerOf4Bytes')

			if i in consumerOf2Bytes:
				consumeNBytes(f, 2)
			elif i in consumerOf4Bytes:
				consumeNBytes(f, 4)

def processTextureList(texList, vol):
	global fSeries
	with open(vol, 'rb') as f:
		for i, offset in enumerate(texList):
			# Caveat: the last texture offset gets stuck.
			if i == MAX_SERIES_TO_EXTRACT:
				print("Stopping at 925th texture offset cause it gets stuck...")
				return
			f.seek(offset, 0)
			#if (fSeries == 1): # debug a single image
			if (fSeries in bgNums): # debug on "BG" images
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

def series_offsets(series):
	if str(series) in hack_offsets:
		tbl = hack_offsets[str(series)]
		consumerOf2Bytes = set(tbl["2"])
		consumerOf4Bytes = set(tbl["4"])
		cel_count = tbl["total_cels"]
		return {'total_cels': cel_count, 'consumerOf2Bytes': consumerOf2Bytes, 'consumerOf4Bytes': consumerOf4Bytes }
	return None

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

def parse_arguments():
	parser = argparse.ArgumentParser(description="A script that handles an audio flag and a series of integers.")

	# Optional boolean flag for debug
	parser.add_argument('--debug', action='store_true', help='Optional boolean flag; enables debugger output')

	# Optional boolean flag for audio
	parser.add_argument('--audio', action='store_true', help='Optional boolean flag for audio')

	# String flag for a series of integers
	parser.add_argument('--series', type=str, help='Comma-delimited list of integers')

	args = parser.parse_args()
	# Convert series to a list of integers if provided
	if args.series:
		series_list = [int(item) for item in args.series.split(',')]
		args.series = set(series_list)

	return args

def loadHackOffsets():
	global hack_offsets
	with open("offsets/hack_offsets.json", "r") as f:
		hack_offsets = json.load(f)

def run():
	global userArgs
	userArgs = parse_arguments()

	loadHackOffsets()

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

	if os.path.exists(f"vol/audio.vol") and userArgs.audio:
		extractAudio("audio.vol")
	else:
		if extractSound:
			print("WARN: 'vol/audio.vol' missing")

if __name__ == "__main__":
	run()

