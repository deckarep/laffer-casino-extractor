# may need to install pillow img ext.
# pip install --upgrade Pillow

import os
import struct
from PIL import Image, ImageFont, ImageDraw

MAX_BYTES_TO_CONSUME = -300_000 # A negative value is simply ignored.
MAX_SCAN_LINES =          -10  # A negative value is simply ignored.
MAX_SERIES_TO_EXTRACT =   -5    # A negative value extracts everything!

font = ImageFont.truetype("SQ3n001.ttf", 25)
fseries = 0
imgSize = 0
totalConsumed = 0
exportPal = False # export palette image to pal/
debug = False # log debug info

def logUnknown(f):
	t = ['<h', '<H', '<b', '<B']
	for x in t:
		f.seek(-8, 1)
		u = []
		m = 0
		i = 0
		b = 0
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

def exportPalImg(f, pal):
	i = 0
	x = 0
	y = 0
	scale = 100 # output pixel size
	im = Image.new('RGB', (16*scale, 16*scale), (255, 255, 255))
	draw = ImageDraw.Draw(im)
	while (i<256):
		p = i * 3
		r = pal[p]
		g = pal[p + 1]
		b = pal[p + 2]
		draw.rectangle((x*scale, y*scale, x*scale+scale, y*scale+scale), fill=(r, g, b))
		if debug:
			print("idx: " + str(i) + " r: "+str(r)+", g: "+str(g)+", b: "+str(b))
			draw.text((x*scale, y*scale), str(i) + " " + hex(i), (255,255,255), font=font) # add numbers on top color
			draw.text((x*scale, y*scale+15), str(i) + " " + hex(i), (0,0,0), font=font) # add black for higher contrast
			draw.text((x*scale, y*scale+30), str(r) + " " + str(g) + " " + str(b), (255,255,255), font=font) # RGB white
			draw.text((x*scale, y*scale+45), str(r) + " " + str(g) + " " + str(b), (0,0,0), font=font) # RGB black
		x += 1
		if (x > 16):
			x = 0
			y += 1
		i += 1
	os.makedirs("pal", exist_ok = True)
	s = f"pal/pal_{fseries}.png"
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

def doReg(kind, f, pal, draw, width, height):
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
	i = 0
	pal = []
	while ( i < 768):
		c = consumeSingleByte(f)
		pal.append(c)
		i += 1
	if exportPal and not os.path.exists(f"pal/{series}_Pal.png"):
		exportPalImg(f, pal)

	# This unknown contains texture's frame count.
	unknown = consumeNBytes(f, 4)
	if debug:
		print(f"fSeries: {fseries} unknown: {unknown}")
		print(f"unknown[2]: {unknown[2]}")
		logUnknown(f)
	NUM_IMAGES = unknown[2]
	
	# Handle each image
	# TODO: extract NUM_IMAGES from somewhere above.
	# Observation: subsprites in a series can have different width/height vals.
	#	so to make it easy, I'm just generating single files and not atlases.
	# Observation: For Peter test file, I confirmed that it spits out 2 duplicate images
	# so it's really just 10 unique animation sprites. Verified with md5 check.
	i = 0
	width = struct.unpack('<H', consumeNBytes(f, 2))[0]
	height = struct.unpack('<H', consumeNBytes(f, 2))[0]
	for i in range(NUM_IMAGES):
		if debug:
			print("width: " + str(width) + ", height: " + str(height))
			print("unknown + width + height consumed: " + str(totalConsumed))
		
		imgSize = width * height
		im = Image.new('RGB', (width, height), (255, 255, 255))
		draw = ImageDraw.Draw(im)
		
		SKIP_BYTES = 8 # originally 8
		consumeNBytes(f, SKIP_BYTES)
		if debug:
			print('arbitrary consumed: ' + str(totalConsumed))

		doReg('reg', f, pal, draw, width, height)

		os.makedirs("img", exist_ok = True)
		s = f"img/sprite_{series}_{i}.png"
		im.save(s, quality=100)
		print("saved " + s)
		if debug:
			print("stopped at: " + str(f.tell()))

def scanResource(vol):
	global fseries
	with open(vol, "rb") as f:
		while (byte := consumeNBytes(f, 1)):
			if (byte == b'\x74' and consumeNBytes(f, 1) == b'\x65' and consumeNBytes(f, 1) == b'\x78' and
				consumeNBytes(f, 1) == b'\x20' and consumeNBytes(f, 1) == b'\x30' and consumeNBytes(f, 1) == b'\x30' and 
				consumeNBytes(f, 1) == b'\x30' and consumeNBytes(f, 1) == b'\x31'):
				if debug:
					print("Found tex 0001, fnum: " + str(fseries) + " starting at: " + str(f.tell()-8))
				if fseries > MAX_SERIES_TO_EXTRACT and MAX_SERIES_TO_EXTRACT > -1:
					print(f"Extracted {MAX_SERIES_TO_EXTRACT - 1} so bailing early...")
					return
				processTexture(f, fseries)
				totalConsumed = 0
				fseries += 1

if __name__ == "__main__":
	# scanResource("test_textures/peter_texture_isolated.bin")
	# Scanning the whole volume is not yet working... :(
	scanResource("vol/RESOURCE.VOL")


