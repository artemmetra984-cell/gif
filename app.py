import os
import subprocess
import tempfile
import requests
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

OVERLAY_URL = os.environ.get('GIF_URL', '')


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/process', methods=['POST'])
def process_video():
    if 'video' not in request.files:
        return jsonify({'error': 'video file required'}), 400

    if not OVERLAY_URL:
        return jsonify({'error': 'GIF_URL env variable not set'}), 500

    video_file = request.files['video']

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input.mp4')
        overlay_path = os.path.join(tmpdir, 'overlay.tmp')
        output_path = os.path.join(tmpdir, 'output.mp4')

        video_file.save(input_path)

        # Download overlay (GIF or video), follow redirects
        r = requests.get(OVERLAY_URL, timeout=30, allow_redirects=True)
        r.raise_for_status()
        with open(overlay_path, 'wb') as f:
            f.write(r.content)

        # Overlay looping at 1/3 from bottom, centered horizontally
        # Works with GIF, MP4, MOV — FFmpeg auto-detects format from content
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-stream_loop', '-1',
            '-i', overlay_path,
            '-filter_complex',
            '[1:v]scale=iw*0.45:-1[ovr];[0:v][ovr]overlay=x=(W-w)/2:y=H*2/3',
            '-shortest',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            return jsonify({'error': result.stderr[-3000:]}), 500

        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name='processed.mp4'
        )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
