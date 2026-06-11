"""快速测试核心逻辑"""
import sys, os, struct
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from video_fingerprint_gui import modify_mp4_metadata

def make_test_mp4(path):
    with open(path, 'wb') as f:
        ftyp_data = b'isom' + b'\x00\x00\x02\x00' + b'isomiso2mp41'
        ftyp_size = 8 + len(ftyp_data)
        f.write(struct.pack('>I', ftyp_size) + b'ftyp' + ftyp_data)
        
        mvhd = b'\x00' * 100
        moov_data = struct.pack('>I', 8 + len(mvhd)) + b'mvhd' + mvhd
        moov_size = 8 + len(moov_data)
        f.write(struct.pack('>I', moov_size) + b'moov' + moov_data)
        
        mdat_data = os.urandom(1024)
        mdat_size = 8 + len(mdat_data)
        f.write(struct.pack('>I', mdat_size) + b'mdat' + mdat_data)

make_test_mp4('test_input.mp4')
print(f'测试文件大小: {os.path.getsize("test_input.mp4")} bytes')

changes = modify_mp4_metadata('test_input.mp4', 'test_output.mp4', {
    'change_uuid': True,
    'change_creation_time': True,
    'change_modification_time': True,
    'random_padding': True,
})

print(f'输出文件大小: {os.path.getsize("test_output.mp4")} bytes')
print(f'修改项 ({len(changes)}):')
for c in changes:
    print(f'  - {c}')

os.remove('test_input.mp4')
os.remove('test_output.mp4')
print('\n[OK] core logic test passed!')
