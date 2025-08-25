from flask import Flask, render_template, request, jsonify, url_for
import os
from werkzeug.utils import secure_filename
import time
from ai_model import process_lottery_image
from utils import check_lottery_number

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Không có file nào được chọn'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Không có file nào được chọn'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Tránh trùng tên file
        timestamp = str(int(time.time()))
        filename = f"{timestamp}_{filename}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Xử lý ảnh bằng AI
        try:
            result = process_lottery_image(filepath)
            result['image_url'] = url_for('static', filename=f'uploads/{filename}')
            result['filename'] = filename  # Để dùng cho manual check
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': f'Lỗi: {str(e)}'}), 500
    
    return jsonify({'error': 'File không hợp lệ. Chỉ chấp nhận PNG, JPG, JPEG, GIF'}), 400

@app.route('/manual_check', methods=['POST'])
def manual_check():
    """API để kiểm tra thủ công khi người dùng nhập đúng thông tin"""
    try:
        data = request.get_json()
        
        # Lấy thông tin từ request
        numbers = data.get('numbers', '').strip()
        lottery_name = data.get('lottery_name', '').strip()
        date = data.get('date', '').strip()
        filename = data.get('filename', '')
        
        # Validate input
        if not numbers or not lottery_name or not date:
            return jsonify({'error': 'Vui lòng điền đầy đủ thông tin'}), 400
        
        if len(numbers) != 6 or not numbers.isdigit():
            return jsonify({'error': 'Số vé phải có đúng 6 chữ số'}), 400
        
        # Kiểm tra format ngày (dd/mm/yyyy)
        try:
            from datetime import datetime
            datetime.strptime(date, '%d/%m/%Y')
        except ValueError:
            return jsonify({'error': 'Ngày phải có format DD/MM/YYYY'}), 400
        
        # Gọi API kiểm tra vé số
        matched = check_lottery_number(numbers, lottery_name, date)
        
        if matched == "EXPIRED":
            result = {
                'ticket_numbers': [numbers],
                'lottery_name': lottery_name,
                'lottery_date': date,
                'results': [],
                'total_prizes': -1,  # Vé hết hạn
                'expired': True,
                'source': 'manual_input'
            }
        elif matched == "NO_RESULTS_YET":
            result = {
                'ticket_numbers': [numbers],
                'lottery_name': lottery_name,
                'lottery_date': date,
                'results': [],
                'total_prizes': -3,  # Chưa có kết quả
                'expired': False,
                'source': 'manual_input'
            }
        elif matched is None:
            result = {
                'ticket_numbers': [numbers],
                'lottery_name': lottery_name,
                'lottery_date': date,
                'results': [],
                'total_prizes': 0,  # Không trúng giải
                'expired': False,
                'source': 'manual_input'
            }
        else:
            result = {
                'ticket_numbers': [numbers],
                'lottery_name': lottery_name,
                'lottery_date': date,
                'results': matched,
                'total_prizes': len(matched),
                'expired': False,
                'source': 'manual_input'
            }
        
        # Thêm thông tin bổ sung
        result['filename'] = filename
        if filename:
            result['image_url'] = url_for('static', filename=f'uploads/{filename}')
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Lỗi khi kiểm tra: {str(e)}'}), 500

@app.route('/save_feedback', methods=['POST'])
def save_feedback():
    """Lưu feedback của người dùng về độ chính xác"""
    try:
        data = request.get_json()
        
        feedback_data = {
            'filename': data.get('filename'),
            'ai_result': {
                'numbers': data.get('ai_numbers'),
                'lottery_name': data.get('ai_lottery_name'),
                'date': data.get('ai_date')
            },
            'correct_result': {
                'numbers': data.get('correct_numbers'),
                'lottery_name': data.get('correct_lottery_name'),
                'date': data.get('correct_date')
            },
            'feedback_type': data.get('feedback_type'),  # 'correct' hoặc 'incorrect'
            'timestamp': time.time()
        }
        
        # Lưu feedback vào file JSON
        feedback_file = 'user_feedback.json'
        feedbacks = []
        
        if os.path.exists(feedback_file):
            try:
                import json
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    feedbacks = json.load(f)
            except:
                feedbacks = []
        
        feedbacks.append(feedback_data)
        
        import json
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedbacks, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'message': 'Đã lưu feedback'})
        
    except Exception as e:
        return jsonify({'error': f'Lỗi lưu feedback: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)