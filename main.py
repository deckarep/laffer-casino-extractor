# may need to install pillow img ext.
# pip install --upgrade Pillow

import os
import struct
from PIL import Image, ImageFont, ImageDraw

font = ImageFont.truetype("SQ3n001.ttf", 25)
fnum = 0
totalConsumed = 0
maxToConsume = 1e9 * 2

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

def consumeByte():
	global totalConsumed
	if totalConsumed >= maxToConsume:
		raise Exception("max bytes consumed")
	result = struct.unpack('<B', f.read(1))[0]
	totalConsumed +=1
	return result

def unconsumeBytes(howMany):
	howMany *= -1
	global totalConsumed
	totalConsumed += howMany
	f.seek(howMany, 1)

def doReg(kind, width, height):
	y = 0
	streamPadding = 0
	while (y < height):
		x = 0
		while (x < width):
			haveRun = False
			try:
				color = consumeByte()
			except Exception as e:
				if str(e) == "max bytes consumed":
					return
				streamPadding +=1
				color = 0

			if color == 0:
				secondColor = consumeByte()
				if secondColor == 0x01:
					runLen = consumeByte()
					haveRun = True
				else:
					unconsumeBytes(1)
					
			#print("color: "+str(color))
			p = color * 3 
			r = pal[p]
			g = pal[p + 1]
			b = pal[p + 2]
			
			# This logging was for the yellow smiley faces and not relevant to peter texture.
			# log color at beginning of row.
			# if (y >= 14 and y <= 15):#(x == 0):
			# 	print("x: " + str(x) + ", y: " + str(y) + ", idx: " + str(color) + ", idx(b): " + format(color, '08b'))
			if haveRun:
				draw.rectangle((x, y, x+runLen, y+1), fill=(r, g, b))
				# Increment x by runLen + however many bytes were consumed.
				x += runLen + 3
			else:
				draw.rectangle((x, y, x+1, y+1), fill=(r, g, b))
				x += 1
		y += 1
	
	print("WARN: stream padded with: " + str(streamPadding) + " bytes!!")

with open("peter_texture_isolated.bin", "rb") as f:
	while (byte := f.read(1)):
		if (byte == b'\x74' and f.read(1) == b'\x65' and f.read(1) == b'\x78' and
	  		f.read(1) == b'\x20' and f.read(1) == b'\x30' and f.read(1) == b'\x30' and 
			f.read(1) == b'\x30' and f.read(1) == b'\x31'):
			print("Found tex 0001, fnum: " + str(fnum) + " starting at: " + str(f.tell()-8))
			
			i = 0
			pal = []
			while ( i < 768):
				c = consumeByte()
				pal.append(c)
				i += 1
			
			#if not os.path.exists("pal/0_Pal.png"):
			exportPalImg()
			
			unknown = f.read(4)
			logUnknown(f)
			#print("unknown: " + str(unknown))
			width = struct.unpack('<H', f.read(2))[0]
			height = struct.unpack('<H', f.read(2))[0]
			print("width: " + str(width) + ", height: " + str(height))
			
			xPadding = 0
			yPadding = 0
			widthFactor = 1
			heightFactor = 1
			padding = True
			
			if padding:
				width = (width * widthFactor) + xPadding
				height = (height * heightFactor) + yPadding
			
			imgSize = width * height
			im = Image.new('RGB', (width, height), (255, 255, 255))
			draw = ImageDraw.Draw(im)
			
			bytesToSkip = 19 # originally 8
			f.read(bytesToSkip)

			#doRLE('rle', imgSize, width)
			doReg('reg', width, height)

			s = "img/" + str(fnum) + '.png'
			im.save(s, quality=95)
			fnum += 1
			print("stopped at: " + str(f.tell()))