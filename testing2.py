from collections import Counter

def decompress_sci1_rle(data):
    decompressed = []
    i = 0

    while i < len(data):
        byte = data[i]
        xx = byte >> 6
        yyyyyy = byte & 0x3F

        if xx == 0b00:
            # Case A: Copy next YYYYYY bytes as-is
            decompressed.extend(data[i + 1: i + 1 + yyyyyy])
            i += 1 + yyyyyy
        elif xx == 0b01:
            # Case B: Copy YYYYYY + 64 bytes as-is
            decompressed.extend(data[i + 1: i + 1 + yyyyyy + 64])
            i += 1 + yyyyyy + 64
        elif xx == 0b10:
            # Case C: Set the next YYYYYY pixels to the next byte value
            decompressed.extend([data[i + 1]] * yyyyyy)
            i += 2
        elif xx == 0b11:
            # Case D: Skip the next YYYYYY pixels (transparency)
            decompressed.extend([0x00] * yyyyyy)
            i += 1
        else:
            i += 1

    return decompressed

# Provided example data
hex_data = [
    0x01, 0x35, 0x00, 0x08, 0x08, 0x00, 0xE9, 0x02, 0x02, 0x00, 0xE6, 0xE6, 0x01, 0x28, 0x00
]

# Decompress the data
decompressed_data = decompress_sci1_rle(hex_data)

# Print the decompressed data
decompressed_data_length = len(decompressed_data)
decompressed_data_sample = decompressed_data[:60]  # First 60 entries to cross-verify

# To verify, let's print counts
decompressed_data_counts = Counter(decompressed_data)

print("Decompressed Data Length:", decompressed_data_length)
print("Decompressed Data Sample:", decompressed_data_sample)
print("Decompressed Data Counts:", decompressed_data_counts)
