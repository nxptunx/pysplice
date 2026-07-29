
def decode_splice_audio(data: bytes) -> bytearray:
    arr = bytearray(data)
    
    size_data = arr[2:10]
    size = 0
    for b in reversed(size_data):
        size = (256 * size) + b
    
    encoding_data = arr[10:28]
    encode_blk = encoding_data.decode('latin-1')
    
    audio_data = arr[28:]
    
    def decode_pass(start_idx: int, arr: bytearray, encode_blk: str, limit: int) -> int:
        encblk_len = len(encode_blk)
        encblk_idx = 0
        i = start_idx
        
        while i < limit:
            if encblk_idx >= encblk_len:
                encblk_idx = 0 # wraparound
            
            if i < len(arr):
                arr[i] = arr[i] ^ ord(encode_blk[encblk_idx])
            
            i += 1
            encblk_idx += 1
        return i

    pass_idx = decode_pass(0, audio_data, encode_blk, size)
    pass_idx += size
    
    decode_pass(pass_idx, audio_data, encode_blk, pass_idx + size)
    
    return audio_data

if __name__ == "__main__":
    
import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "rb") as f:
            data = f.read()
            decoded = decode_splice_audio(data)
            with open("decoded_" + sys.argv[1], "wb") as out:
                out.write(decoded)
            print(f"Decoded {sys.argv[1]} to decoded_{sys.argv[1]}")
