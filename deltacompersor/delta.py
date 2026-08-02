import os
from helper import read_file
from matcher import Matcher
from operations import OperationGenerator
from encoder import Encoder
from serializer import Serializer
from decoder import Decoder
from verifier import Verifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(filename):
    return os.path.join(BASE_DIR, filename)

# Read files in delta_compressor directory
old_text = read_file(get_path("old.txt"))
new_text = read_file(get_path("new.txt"))

# Compare delta
matcher = Matcher()
opcodes = matcher.compare(old_text, new_text)

# Generate operations using the OperationGenerator
generator = OperationGenerator()
operations = generator.generate(opcodes, old_text, new_text)

# Encode the operations into a delta format
encoder = Encoder()
delta = encoder.encode(operations)

# Save JSON the delta to a file using the Serializer
serializer = Serializer()
serializer.save(delta, get_path("output/delta.json"))

# Load JSON the delta from a file using the Serializer
delta = serializer.load(get_path("output/delta.json"))

# Decode using the Decoder to reconstruct the new text from the old text and the delta
decoder = Decoder()
reconstructed = decoder.decode(old_text, delta)

# Verify the delta compression by comparing the reconstructed text with the new text using the Verifier
verifier = Verifier()

if verifier.verify(reconstructed, new_text):
    print("Delta Compression Successful")
    print(reconstructed)
else:
    print("Verification Failed")