# may need to install pillow img ext.
# pip install --upgrade Pillow

import os
import struct
from PIL import Image, ImageFont, ImageDraw

font = ImageFont.truetype("SQ3n001.ttf", 25)
fnum = 0
MAX_BYTES_TO_CONSUME = 300_000
totalConsumed = 0
MAX_SCAN_LINES = -10

# Observed patterns so far
# 1. byte:00, byte:01, byte:<run count>, byte:<color idx> - used for transparency.
# 2. Literal run pattern:
#	[0002] - marks a literal run
#   [byte or 2byte] - how many in the literal run
#   [.....] - the actual bytes as color indices in the run
# 2. 0002 after every compression run except the first? Not sure if this is for sure. 


def logUnknown(f):
	f.seek(-8, 1)
	u2 = struct.unpack('<h', f.read(2))[0]
	u3 = struct.unpack('<h', f.read(2))[0]
	u4 = struct.unpack('<h', f.read(2))[0]
	u5 = struct.unpack('<h', f.read(2))[0]
	print("  0x310: as 4 s16: " + str(u2)+", "+str(u3)+", "+str(u4)+", "+str(u5))
	f.seek(-8, 1)
	u2 = struct.unpack('<H', f.read(2))[0]
	u3 = struct.unpack('<H', f.read(2))[0]
	u4 = struct.unpack('<H', f.read(2))[0]
	u5 = struct.unpack('<H', f.read(2))[0]
	print("  0x310: as 4 u16: " + str(u2)+", "+str(u3)+", "+str(u4)+", "+str(u5))
	f.seek(-8, 1)
	u2 = struct.unpack('<b', f.read(1))[0]
	u3 = struct.unpack('<b', f.read(1))[0]
	u4 = struct.unpack('<b', f.read(1))[0]
	u5 = struct.unpack('<b', f.read(1))[0]
	u6 = struct.unpack('<b', f.read(1))[0]
	u7 = struct.unpack('<b', f.read(1))[0]
	u8 = struct.unpack('<b', f.read(1))[0]
	u9 = struct.unpack('<b', f.read(1))[0]
	print("  0x310: as 8 s8:  " + str(u2)+", "+str(u3)+", "+str(u4)+", "+str(u5)+", "+str(u6)+", "+str(u7)+", "+str(u8)+", "+str(u9))
	f.seek(-8, 1)
	u2 = struct.unpack('<B', f.read(1))[0]
	u3 = struct.unpack('<B', f.read(1))[0]
	u4 = struct.unpack('<B', f.read(1))[0]
	u5 = struct.unpack('<B', f.read(1))[0]
	u6 = struct.unpack('<B', f.read(1))[0]
	u7 = struct.unpack('<B', f.read(1))[0]
	u8 = struct.unpack('<B', f.read(1))[0]
	u9 = struct.unpack('<B', f.read(1))[0]
	print("  0x310: as 8 u8:  " + str(u2)+", "+str(u3)+", "+str(u4)+", "+str(u5)+", "+str(u6)+", "+str(u7)+", "+str(u8)+", "+str(u9))

def exportPalImg():
	i = 0
	x = 0
	y = 0
	scale = 100
	im = Image.new('RGB', (16*scale, 16*scale), (255, 255, 255))
	draw = ImageDraw.Draw(im)
	while (i<256):
		p = i * 3
		r = pal[p]
		g = pal[p + 1]
		b = pal[p + 2]
		print("idx: " + str(i) + " r: "+str(r)+", g: "+str(g)+", b: "+str(b))
		draw.rectangle((x*scale, y*scale, x*scale+scale, y*scale+scale), fill=(r, g, b))
		draw.text((x*scale, y*scale), str(i) + " " + hex(i), (255,255,255), font=font) # add numbers on top color
		draw.text((x*scale, y*scale+15), str(i) + " " + hex(i), (0,0,0), font=font) # add black for higher contrast
		draw.text((x*scale, y*scale+30), str(r) + " " + str(g) + " " + str(b), (255,255,255), font=font) # RGB white
		draw.text((x*scale, y*scale+45), str(r) + " " + str(g) + " " + str(b), (0,0,0), font=font) # RGB black
		x += 1
		if (x > 16):
			x = 0
			y += 1
		i += 1
	s = "pal/" + str(fnum) + '_Pal.png'
	im.save(s, quality=100)

def doRLE(kind, imgSize, width):
	x = 0
	y = 0
	print("imgSize: "+str(imgSize))
	while ((x * y) < imgSize):
		repeat = struct.unpack('<B', f.read(1))[0]
		color = struct.unpack('<B', f.read(1))[0]
		#print("repeat: "+str(repeat)+", color: "+str(color))
		p = color * 3
		r = pal[p]
		g = pal[p + 1]
		b = pal[p + 2]
		#print ("r: " + str(r) + ", g: " + str(g) + ", b: " + str(b))
		i = 0
		while (i < repeat):
			draw.rectangle((x, y, x+1, y+1), fill=(r, g, b))
			i += 1
			x += 1
			if (x > width):
				x = 0
				y += 1

def consumeSingleByte():
	global totalConsumed
	if totalConsumed >= MAX_BYTES_TO_CONSUME:
		raise Exception("max bytes consumed")
	result = struct.unpack('<B', f.read(1))[0]
	totalConsumed +=1
	return result

def consumeNBytes(howMany):
	global totalConsumed
	totalConsumed += howMany
	return f.read(howMany)

def unconsumeBytes(howMany):
	howMany *= -1
	global totalConsumed
	f.seek(howMany, 1)
	totalConsumed -= howMany

def doReg(kind, width, height):
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
				singleByte = consumeSingleByte()
			except Exception as e:
				if str(e) == "max bytes consumed":
					return
				streamPadding +=1
				singleByte = 0

			if singleByte == 0x01:
				# Basic case: Single Color Run, often used for transparency.
				# Next byte: <runLen>
				# Next byte: <colorIdx>
				runLen = consumeSingleByte()
				colorIdx = consumeSingleByte()
				haveRun = True
			elif singleByte == 0x02:
				# Literal case: a sequence of differing N literal bytes.
				literalLen = consumeSingleByte()
				zeroDelimiter = consumeSingleByte()
				haveLiteralSeq = True
			elif singleByte == 0x08:
				# Single Color Run: NON-transparency
				runLen = consumeSingleByte()
				zeroDelimiter = consumeSingleByte()
				haveSingleRunNonTransparent = True

			if haveRun:
				p = colorIdx * 3
				r = pal[p] 
				g = pal[p + 1]
				b = pal[p + 2]
				draw.rectangle((x, y, x+runLen, y+1), fill=(r, g, b))
				print(f"Run: x={x}, y={y}, runLen={runLen} (0x{runLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
				# Increment x by runLen + however many bytes were consumed.
				x += runLen# + 3
			elif haveLiteralSeq:
				for i in range(literalLen):
					colorIdx = consumeSingleByte()
					p = colorIdx * 3
					r = pal[p]
					g = pal[p + 1] 
					b = pal[p + 2]
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					print(f"Literal: x={x}, y={y}, litLen={literalLen} (0x{literalLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
					x +=1
				# BUG HERE: STILL SEEING ARTIFACTS with this logic!
				# TODO: FIXME!
				#x += 3 # BUG?????: since I consumed bytes above for a literal, do i need to inc x?
			elif haveSingleRunNonTransparent:
				colorIdx = consumeSingleByte()
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
	
	print("WARN: stream padded with: " + str(streamPadding) + " bytes!!")

with open("peter_texture_isolated.bin", "rb") as f:
	while (byte := consumeNBytes(1)):
		if (byte == b'\x74' and consumeNBytes(1) == b'\x65' and consumeNBytes(1) == b'\x78' and
	  		consumeNBytes(1) == b'\x20' and consumeNBytes(1) == b'\x30' and consumeNBytes(1) == b'\x30' and 
			consumeNBytes(1) == b'\x30' and consumeNBytes(1) == b'\x31'):
			print("Found tex 0001, fnum: " + str(fnum) + " starting at: " + str(f.tell()-8))

			print("magic consumed: " + str(totalConsumed))
			
			i = 0
			pal = []
			while ( i < 768):
				c = consumeSingleByte()
				pal.append(c)
				i += 1
			
			print("palette consumed: " + str(totalConsumed))
			if not os.path.exists("pal/0_Pal.png"):
				exportPalImg()
			
			unknown = consumeNBytes(4)
			logUnknown(f)
			#print("unknown: " + str(unknown))
			width = struct.unpack('<H', consumeNBytes(2))[0]
			height = struct.unpack('<H', consumeNBytes(2))[0]
			print("width: " + str(width) + ", height: " + str(height))

			print("unknown + width + height consumed: " + str(totalConsumed))
			
			rowFactor = 20

			imgSize = width * (height * rowFactor)
			im = Image.new('RGB', (width, (height * rowFactor)), (255, 255, 255))
			draw = ImageDraw.Draw(im)
			
			SKIP_BYTES = 8 # originally 8
			consumeNBytes(SKIP_BYTES)
			print('arbitrary consumed: ' + str(totalConsumed))

			doReg('reg', width, (height * rowFactor))

			s = "img/" + str(fnum) + '.png'
			im.save(s, quality=100)
			fnum += 1
			print("stopped at: " + str(f.tell()))