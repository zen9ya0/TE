from flask import Flask, request, jsonify, render_template
import os
from datetime import datetime, timedelta
from upload_file_cli import upload_file_to_threat_prevention, query_threat_prevention
from utils.file_manager import FileManager
from mail_analyzer import MailAnalyzer
from werkzeug.utils import secure_filename
import threading
import uuid
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import time

app = Flask(__name__)

# 初始化檔案管理器（設定 1 分鐘後自動清理）
file_manager = FileManager(retention_minutes=1)

# 設定
ALLOWED_EXTENSIONS = {'tif','exe', 'dll', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', '7z','txt','csv','js','php','html','css','sql','xml','json','yaml','yml','ini','log','md','sh','bat','ps1','ps2','ps3','ps4','ps5','ps6','ps7','ps8','ps9','ps10', 'eml', 'msg'}
API_KEY = "{YOUR API KEY}"
UPLOAD_FOLDER = '/tmp/analytic_file'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 用於儲存分析狀態的字典
mail_analysis_status = {}

# 批次分析狀態追蹤
batch_analysis_status = {}

# 設定最大同時執行的執行緒數
MAX_WORKERS = 5
# 初始化執行緒池
upload_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_md5(file_path):
    """計算檔案的 MD5"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def format_time_duration(start_time, end_time):
    """格式化時間差"""
    if not start_time or not end_time:
        return "N/A"
    
    duration = end_time - start_time
    seconds = duration.total_seconds()
    
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} 分鐘"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} 小時"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'message': '未找到上傳的檔案'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'status': 'error',
                'message': '未選擇檔案'
            }), 400

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'message': '不支援的檔案類型'
            }), 400

        # 使用 FileManager 保存檔案
        file_info = file_manager.save_file(file)
        
        # 使用 upload_file_cli.py 的功能進行分析
        result = upload_file_to_threat_prevention(API_KEY, file_info['path'])
        
        # 將檔案資訊加入結果中
        if 'response' in result and len(result['response']) > 0:
            result['response'][0]['file_info'] = file_info

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'處理檔案時發生錯誤: {str(e)}'
        }), 500

@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json()
        if not data or 'query_id' not in data:
            return jsonify({
                'status': 'error',
                'message': '未提供查詢 ID'
            }), 400

        query_id = data['query_id'].strip()
        if not query_id:
            return jsonify({
                'status': 'error',
                'message': '查詢 ID 不能為空'
            }), 400

        result = query_threat_prevention(API_KEY, query_id)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'查詢時發生錯誤: {str(e)}'
        }), 500

@app.route('/mail_status/<mail_id>', methods=['GET'])
def get_mail_status(mail_id):
    if mail_id not in mail_analysis_status:
        return jsonify({
            'status': 'error',
            'message': '找不到指定的分析記錄'
        }), 404
    
    return jsonify(mail_analysis_status[mail_id])

@app.route('/analyze_mail', methods=['POST'])
def analyze_mail():
    if 'file' not in request.files:
        return jsonify({
            'status': 'error',
            'message': '未找到檔案'
        }), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'status': 'error',
            'message': '未選擇檔案'
        }), 400

    try:
        mail_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # 保存上傳的檔案
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{filename}"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
        file.save(temp_path)

        # 計算 MD5
        file_md5 = calculate_md5(temp_path)

        # 初始化狀態
        mail_analysis_status[mail_id] = {
            'status': 'analyzing',
            'filename': filename,
            'md5': file_md5,
            'attachments': [],
            'timestamp': start_time.isoformat(),
            'start_time': start_time.isoformat(),
            'duration': None
        }

        # 在背景執行分析
        def analyze_in_background():
            try:
                analyzer = MailAnalyzer(output_dir=UPLOAD_FOLDER)
                result = analyzer.analyze_mail(temp_path)
                
                end_time = datetime.now()
                duration = format_time_duration(start_time, end_time)
                
                if result['status'] == 'success':
                    attachments = []
                    for analysis in result['analysis_results']:
                        attachment_start = datetime.now()
                        attachment_info = {
                            'original_name': analysis['original_name'],
                            'status': 'analyzing',
                            'md5': None,
                            'verdict': 'unknown',
                            'start_time': attachment_start.isoformat(),
                            'duration': None
                        }
                        
                        # 獲取附件 MD5
                        if os.path.exists(analysis['saved_path']):
                            attachment_info['md5'] = calculate_md5(analysis['saved_path'])
                        
                        # 獲取判定結果
                        if 'query_result' in analysis:
                            query_result = analysis['query_result']
                            if 'response' in query_result and query_result['response']:
                                response = query_result['response'][0]
                                if 'te' in response:
                                    attachment_info['verdict'] = response['te'].get('combined_verdict', 'unknown')
                                    attachment_info['status'] = 'completed'
                        
                        attachment_end = datetime.now()
                        attachment_info['duration'] = format_time_duration(
                            attachment_start, 
                            attachment_end
                        )
                        attachments.append(attachment_info)
                    
                    mail_analysis_status[mail_id].update({
                        'status': 'completed',
                        'attachments': attachments,
                        'duration': duration
                    })
                else:
                    mail_analysis_status[mail_id].update({
                        'status': 'error',
                        'message': result.get('error_message', '分析失敗'),
                        'duration': duration
                    })
                
                # 清理暫存檔
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
            except Exception as e:
                end_time = datetime.now()
                mail_analysis_status[mail_id].update({
                    'status': 'error',
                    'message': str(e),
                    'duration': format_time_duration(start_time, end_time)
                })

        thread = threading.Thread(target=analyze_in_background)
        thread.start()

        return jsonify({
            'status': 'success',
            'message': '檔案已開始分析',
            'id': mail_id
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'處理檔案時發生錯誤: {str(e)}'
        }), 500

@app.route('/mail_analysis_list', methods=['GET'])
def get_mail_analysis_list():
    """獲取所有分析任務的列表"""
    analysis_list = []
    for mail_id, status in mail_analysis_status.items():
        analysis_list.append({
            'id': mail_id,
            **status
        })
    
    # 按時間戳記排序，最新的在前
    analysis_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(analysis_list)

@app.route('/favicon.ico')
def favicon():
    return app.send_from_directory('static/images',
                                 'favicon.ico', 
                                 mimetype='image/vnd.microsoft.icon')

def process_file(file, batch_id):
    """處理單個檔案的上傳和分析"""
    file_start_time = datetime.now()
    filename = secure_filename(file.filename)
    temp_path = os.path.join(UPLOAD_FOLDER, filename)
    
    file_info = {
        'filename': filename,
        'status': 'analyzing',
        'start_time': file_start_time.isoformat(),
        'duration': None,
        'md5': None,
        'result': None,
        'verdict': 'unknown',
        'combined_verdict': {
            'status': 'unknown',
            'severity': 'unknown',
            'confidence': 'unknown'
        }
    }
    
    try:
        # 保存檔案
        file.save(temp_path)
        file_info['md5'] = calculate_md5(temp_path)
        
        # 執行分析
        result = upload_file_to_threat_prevention(API_KEY, temp_path)
        
        # 解析判定結果
        if result.get('response') and len(result['response']) > 0:
            response = result['response'][0]
            if 'te' in response:
                te_data = response['te']
                file_info['combined_verdict'] = {
                    'status': te_data.get('combined_verdict', 'unknown'),
                    'severity': te_data.get('severity', 'unknown'),
                    'confidence': te_data.get('confidence', 'unknown')
                }
                file_info['verdict'] = te_data.get('combined_verdict', 'unknown')
        
        file_end_time = datetime.now()
        file_info.update({
            'status': 'completed',
            'result': result,
            'duration': format_time_duration(file_start_time, file_end_time)
        })
        
    except Exception as e:
        file_end_time = datetime.now()
        file_info.update({
            'status': 'error',
            'error': str(e),
            'duration': format_time_duration(file_start_time, file_end_time),
            'verdict': 'error',
            'combined_verdict': {
                'status': 'error',
                'severity': 'unknown',
                'confidence': 'unknown'
            }
        })
    
    finally:
        # 清理暫存檔
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        
        # 更新批次狀態
        with app.app_context():
            batch_status = batch_analysis_status.get(batch_id)
            if batch_status:
                batch_status['files'].append(file_info)
                batch_status['completed_files'] += 1
                
                # 檢查是否所有檔案都處理完成
                if batch_status['completed_files'] >= batch_status['total_files']:
                    end_time = datetime.now()
                    batch_status.update({
                        'status': 'completed',
                        'duration': format_time_duration(
                            datetime.fromisoformat(batch_status['start_time']), 
                            end_time
                        )
                    })
    
    return file_info

@app.route('/batch_upload', methods=['POST'])
def batch_upload():
    if 'files[]' not in request.files:
        return jsonify({'error': '未找到檔案'}), 400
    
    files = request.files.getlist('files[]')
    batch_id = str(uuid.uuid4())
    start_time = datetime.now()
    
    # 初始化批次狀態
    batch_analysis_status[batch_id] = {
        'status': 'processing',
        'files': [],
        'start_time': start_time.isoformat(),
        'duration': None,
        'total_files': len(files),
        'completed_files': 0
    }
    
    # 使用執行緒池處理檔案
    futures = []
    for file in files:
        future = upload_executor.submit(process_file, file, batch_id)
        futures.append(future)
    
    # 非阻塞方式等待所有任務完成
    def wait_for_completion():
        try:
            # 等待所有任務完成
            for future in as_completed(futures):
                try:
                    future.result()  # 獲取結果（如果有錯誤會拋出）
                except Exception as e:
                    print(f"處理檔案時發生錯誤: {str(e)}")
        except Exception as e:
            print(f"等待任務完成時發生錯誤: {str(e)}")
    
    # 在背景執行等待
    threading.Thread(target=wait_for_completion).start()
    
    return jsonify({
        'status': 'success',
        'batch_id': batch_id,
        'message': '批次處理已開始'
    })

@app.route('/batch_status/<batch_id>', methods=['GET'])
def get_batch_status(batch_id):
    if batch_id not in batch_analysis_status:
        return jsonify({'error': '找不到指定的批次處理記錄'}), 404
    
    status = batch_analysis_status[batch_id]
    return jsonify({
        'status': status['status'],
        'total_files': status['total_files'],
        'completed_files': status['completed_files'],
        'duration': status['duration'],
        'files': sorted(status['files'], key=lambda x: x['filename'])
    })

@app.route('/clear_mail_status', methods=['POST'])
def clear_mail_status():
    """清除所有郵件分析狀態"""
    try:
        mail_analysis_status.clear()
        return jsonify({
            'status': 'success',
            'message': '分析狀態已清除'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'清除狀態時發生錯誤: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True) 
