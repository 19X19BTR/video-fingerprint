"""测试指纹修改是否真的能生成文件"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from video_fingerprint_gui import fingerprint_video

def make_test_mp4(path):
    """创建一个最小的有效 MP4"""
    with open(path, 'wb') as f:
        # ftyp
        ftyp = b'isom' + b'\x00\x00\x02\x00' + b'isomiso2mp41'
        f.write(struct.pack('>I', 8 + len(ftyp)) + b'ftyp' + ftyp)
        # moov with mvhd
        mvhd = b'\x00' * 100
        mvhd_box = struct.pack('>I', 8 + len(mvhd)) + b'mvhd' + mvhd
        f.write(struct.pack('>I', 8 + len(mvhd_box)) + b'moov' + mvhd_box)
        # mdat
        mdat = os.urandom(512)
        f.write(struct.pack('>I', 8 + len(mdat)) + b'mdat' + mdat)

src = 'test_src.mp4'
make_test_mp4(src)
print(f'Source: {os.path.getsize(src)} bytes')

dst = 'test_dst.mp4'
changes = fingerprint_video(src, dst)
print(f'Output: {os.path.getsize(dst)} bytes')
print(f'Changes: {changes}')

# Verify output is different
with open(src, 'rb') as f:
    src_data = f.read()
with open(dst, 'rb') as f:
    dst_data = f.read()
print(f'Different from source: {src_data != dst_data}')

os.remove(src)
os.remove(dst)
print('OK')
