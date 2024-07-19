def decompress(data):
    decompressed = []
    i = 0

    while i < len(data):
        if data[i] == 0x01:
            # Run-length encoding
            run_count = data[i + 1]
            color_index = data[i + 2]
            decompressed.extend([color_index] * run_count)
            i += 3
        else:
            # Literal sequence
            color_index = data[i]
            decompressed.append(color_index)
            i += 1

    return decompressed

# Provided example data
hex_data = [
    0x01, 0x35, 0x00, 0x08, 0x08, 0x00, 0xE9, 0x02, 0x02, 0x00, 0xE6, 0xE6, 0x01, 0x28, 0x00
]

# Decompress the data
decompressed_data = decompress(hex_data)

# Print the decompressed data
print(decompressed_data)

# To verify, let's print counts
from collections import Counter
print(Counter(decompressed_data))
