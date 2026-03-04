# requires pillow img ext.
# pip install --upgrade Pillow

import argparse
import os
import struct
import json
import pdb
from PIL import Image, ImageFont, ImageDraw

from dataclasses import asdict, dataclass

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

# Counters
cels_extracted = 0
warn_cels_skipped = 0

resourceVolFile = "RESOURCE.VOL"

def _read_u32_le(f) -> int:
	b = f.read(4)
	return struct.unpack('<I', b)[0]

def _read_u16_le(f) -> int:
	b = f.read(2)
	return struct.unpack('<H', b)[0]

def _read_cstring(f) -> str:
	buf = bytearray()
	foundEnd = False
	while not foundEnd:
		ch = f.read(1)
		if ch == b"\x00":
			foundEnd = True
		else:
			buf += ch
	return buf.decode('ascii')

@dataclass(frozen=True)
class ChunkRecord:
	index: int
	unknown: int
	name: str
	size: int
	offset: int
	data_start: int
	data_end: int

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
	# Each row of the image starts with a uint16 rowBytes
	# followed by rowBytes bytes containing 1 byte opcodes
	# and 2-byte low-endian run lengths:
	#
	# 01 lo hi
	#     paints a predetermined for the run (color 0/transparency?)
	#
	# 02 lo hi <payload>
	#     paints 1 pixel at a time, reading a color byte for each one
	#
	# 08 lo hi color
	#     paints a specified color for the run

	y = 0
	while y < height:
		x = 0
		row_bytes = _read_u16_le(f)
		while x < width:
			opcode = consumeSingleByte(f)
			runLen = _read_u16_le(f)

			colorIdx = 0

			if opcode == 0x08:
				colorIdx = consumeSingleByte(f)

			if opcode != 0x02:
				p = colorIdx * 3
				r = pal[p] 
				g = pal[p + 1]
				b = pal[p + 2]
				draw.rectangle((x, y, x+runLen, y+1), fill=(r, g, b))
				if debug:
					print(f"Run: x={x}, y={y}, runLen={runLen} (0x{runLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
				x += runLen
			else:
				for i in range(runLen):
					colorIdx = consumeSingleByte(f)
					p = colorIdx * 3
					r = pal[p]
					g = pal[p + 1] 
					b = pal[p + 2]
					draw.rectangle((x, y, x + 1, y+1), fill=(r, g, b))
					if debug:
						print(f"Literal: x={x}, y={y}, litLen={literalLen} (0x{literalLen:x}), colorIdx={colorIdx} (0x{colorIdx:x})")
					x += 1
		y += 1

def processTexture(f, series, texInfo):
	f.seek(texInfo.data_start)

	# Filter by single series.
	if userArgs.series and len(userArgs.series) > 0:
		if series not in userArgs.series:
			return

	# consume the "tex 0001" at the beginning
	consumeNBytes(f, 8)

	# Palette
	i = 0
	pal = []
	while ( i < 768):
		c = consumeSingleByte(f)
		pal.append(c)
		i += 1
	if exportPal and not os.path.exists(f"pal/{series}_Pal.png"):
		exportPalImg(series, pal)

	# right after the palette is a count of image "groups"
	num_image_groups = _read_u16_le(f)

	# Note: some groups have 0 images in them
	# if image count > 0, the group data starts with a count of the images in the group
	# followed by a header for each image:
	#   uint16 width
	#   uint16 height
	#   uint16 unknown1 <--\
	#   uint16 unknown2 <-- \ these values have 0's for most images but not all, purpose unknown for now
	#   uint16 unknown3 <-- /
	#   uint16 unknown4 <--/
	endOfCel = 0
	for i in range(num_image_groups):
		group_image_count = _read_u16_le(f)
		if group_image_count != 0:
			for j in range(group_image_count):
				#read image header
				width = _read_u16_le(f)
				height = _read_u16_le(f)
				unknown1 = _read_u16_le(f)
				unknown2 = _read_u16_le(f)
				unknown3 = _read_u16_le(f)
				unknown4 = _read_u16_le(f)

				#process image
				im = Image.new('RGB', (width, height), (255, 255, 255))
				draw = ImageDraw.Draw(im)

				celOffset = f.tell()

				doRLE(f, pal, draw, width, height)

				endOfCel = f.tell()

				os.makedirs("img", exist_ok = True)
				s = f"img/sprite_{series}_{texInfo.name}_{i}_{j}.png"
				im.save(s, quality=100)

				print(f"saved {s} from orig_offset: {texInfo.offset}, cel_offset: {celOffset}")
				global cels_extracted
				cels_extracted +=1

	if texInfo.data_end != endOfCel:
		print("Image data processing stopped before EOF!")

def processTextureList(texList, vol):
	global fSeries
	with open(vol, 'rb') as f:
		for i, texture in enumerate(texList):
			processTexture(f, fSeries, texture)
			fSeries += 1

def findChunks(vol):
	print("Scanning for chunks, please wait...")
	chunkList = []
	directory_records_raw = []

	# Read the .vol file header to build a complete texture list
	# The header starts with 2 32-bit ints:
	# unknown_magic <- possibly a version number?
	# num_chunks    <- number of files within the .vol file
	#
	# Then follows a variable length list of records:
	#          int32 unknown <- maybe a category or something to group files? I haven't compared them but they share a lot of values
	# char[variable] name    <- \0 terminated file name for that chunk
	#          int32 size    <- size of the chunk
	#          int32 offset  <- position of chunk in .vol file relative to the end of the .vol header
	with open(vol, "rb") as f:
		unknown_magic = _read_u32_le(f)
		num_chunks = _read_u32_le(f)
		for i in range(num_chunks):
			unknown = _read_u32_le(f)
			name = _read_cstring(f)
			size = _read_u32_le(f)
			offset = _read_u32_le(f)
			directory_records_raw.append((name, unknown, size, offset))

		# directory offsets are relative to this position:
		chunks_start = f.tell()

	for i, (name, unknown, size, offset) in enumerate(directory_records_raw):
		data_start = chunks_start + offset
		data_end = data_start + size
		chunkList.append(ChunkRecord(i, unknown, name, size, offset, data_start, data_end))

	print(f"Identified {len(chunkList)} individual files!")
	return chunkList

def series_offsets(series):
	if str(series) in hack_offsets:
		tbl = hack_offsets[str(series)]
		consumerOf2Bytes = set(tbl["2"])
		consumerOf4Bytes = set(tbl["4"])
		cel_count = tbl["total_cels"]
		return {'total_cels': cel_count, 'consumerOf2Bytes': consumerOf2Bytes, 'consumerOf4Bytes': consumerOf4Bytes }
	return None

def buildOrLoadOffsetTable(filepath):
	CACHE_FOLDER = "cache"
	CACHE_FILE = f"{filepath.replace('/','_')}_offset_tbl.json"
	os.makedirs(CACHE_FOLDER, exist_ok = True)
	if not os.path.exists(f"{CACHE_FOLDER}/{CACHE_FILE}"):
		offTbl = findChunks(filepath)
		with open(f'{CACHE_FOLDER}/{CACHE_FILE}', 'w') as jf:
			json.dump([asdict(r) for r in offTbl], jf, indent=4)
		return offTbl
	else:
		with open(f'{CACHE_FOLDER}/{CACHE_FILE}', 'r') as jf:
			data = json.load(jf)
			return [ChunkRecord(**d) for d in data]

def getTexturesFromOffsetTable(offTbl):
	onlyTextures = [e for e in offTbl if ".tex" in e.name.lower()]
	print(f"Identified {len(onlyTextures)} individual textures!")
	return onlyTextures

def extractBin(offTbl, n):
	# quick and dirty
	with open(os.path.join("vol/",resourceVolFile), 'rb') as f:
		f.seek(offTbl[n].data_start)
		b = f.read(offTbl[n].size)
		s = f"test_textures/{str(n)}_{offTbl[n].name}.bin"
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

	filepath = os.path.join("vol/",resourceVolFile)

	# scanResource("test_textures/peter_texture_isolated.bin")
	if os.path.exists(filepath):
		if extractTextures:
			offTbl = buildOrLoadOffsetTable(filepath)
			texTbl = getTexturesFromOffsetTable(offTbl)
			#extractBin(offTbl, 906)
			processTextureList(texTbl, filepath)
			print(f"Summary - Total Series: {fSeries}, Cels Extracted: {cels_extracted}, Cels Skipped: {warn_cels_skipped}")
		if extractSound:
			extractAudio(filepath)
	else:
		print(f"ERROR: '{filepath}' missing")

	if os.path.exists(f"vol/audio.vol") and userArgs.audio:
		extractAudio("audio.vol")
	else:
		if extractSound:
			print("WARN: 'vol/audio.vol' missing")

if __name__ == "__main__":
	run()

