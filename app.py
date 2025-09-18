from flask import Flask, render_template, request, redirect, url_for, session, g
import sqlite3
import hashlib
app = Flask(__name__)

# Cấu hình ứng dụng
app = Flask(__name__)
app.secret_key = 'your_super_secret_key'  # Thay thế bằng một key ngẫu nhiên và phức tạp

# Đường dẫn đến file cơ sở dữ liệu
DATABASE = 'database.db'

# Hàm kết nối cơ sở dữ liệu
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Cho phép truy cập cột bằng tên
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Hàm khởi tạo cơ sở dữ liệu và thêm dữ liệu mẫu
def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # Tạo bảng Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                name TEXT,
                phone TEXT,
                dob TEXT,
                job_description TEXT,
                role TEXT
            )
        ''')

        # Tạo bảng Rooms
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                location TEXT,
                open_time TEXT,
                capacity INTEGER
            )
        ''')

        # Thêm người dùng mẫu nếu chưa có
        cursor.execute("SELECT * FROM users WHERE username IN ('admin', 'user1')")
        if not cursor.fetchone():
            # Sử dụng hashing để mã hóa mật khẩu
            admin_password = hashlib.sha256('admin_pass'.encode()).hexdigest()
            user1_password = hashlib.sha256('user1_pass'.encode()).hexdigest()

            cursor.execute("INSERT INTO users (username, password, role, name, phone) VALUES (?, ?, ?, ?, ?)",
                           ('admin', admin_password, 'admin', 'Admin User', '0987654321'))
            cursor.execute("INSERT INTO users (username, password, role, name, phone) VALUES (?, ?, ?, ?, ?)",
                           ('user1', user1_password, 'user', 'User One', '0123456789'))

        # Thêm phòng học mẫu nếu chưa có
        cursor.execute("SELECT * FROM rooms")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO rooms (name, location, open_time, capacity) VALUES (?, ?, ?, ?)",
                           ('Phòng 101', 'Tầng 1, Tòa A', '8:00 - 17:00', 50))
            cursor.execute("INSERT INTO rooms (name, location, open_time, capacity) VALUES (?, ?, ?, ?)",
                           ('Phòng 205', 'Tầng 2, Tòa B', '9:00 - 18:00', 30))

        db.commit()

# Khởi tạo DB khi chạy lần đầu
init_db()

# --- Định nghĩa các Routes (Đường dẫn) ---

# Trang Đăng nhập
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
        user = cursor.fetchone()

        if user:
            session['logged_in'] = True
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Tên đăng nhập hoặc mật khẩu không đúng.')
    return render_template('login.html')

# Trang Dashboard
@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard.html', role=session['role'])

# --- Routes cho Quản lý Người dùng ---

# Danh sách Người dùng
@app.route('/users')
def user_list():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    return render_template('user_list.html', users=users, role=session['role'])

# Chi tiết Người dùng
@app.route('/users/<int:user_id>')
def user_detail(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        return render_template('user_detail.html', user=user, role=session['role'])
    return "User not found", 404

# Tạo Người dùng mới (chỉ Admin)
@app.route('/users/create', methods=['GET', 'POST'])
def user_create():
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        dob = request.form.get('dob')
        job_description = request.form.get('job_description')
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        db = get_db()
        db.execute("INSERT INTO users (name, phone, username, password, role, dob, job_description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (name, phone, username, hashed_password, role, dob, job_description))
        db.commit()
        return redirect(url_for('user_list'))
    return render_template('user_edit.html', user=None, role=session['role'])

# Sửa Người dùng (chỉ Admin)
@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
def user_edit(user_id):
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return "User not found", 404

    if request.method == 'POST':
        user_data = request.form
        db.execute("UPDATE users SET name=?, phone=?, dob=?, job_description=?, role=?, username=? WHERE id=?",
                   (user_data['name'], user_data['phone'], user_data['dob'], user_data['job_description'], user_data['role'], user_data['username'], user_id))
        
        # Nếu mật khẩu được nhập, cập nhật mật khẩu mới
        if user_data['password']:
            hashed_password = hashlib.sha256(user_data['password'].encode()).hexdigest()
            db.execute("UPDATE users SET password=? WHERE id=?", (hashed_password, user_id))

        db.commit()
        return redirect(url_for('user_list'))

    return render_template('user_edit.html', user=user, role=session['role'])

# Xóa Người dùng (chỉ Admin)
@app.route('/users/delete/<int:user_id>', methods=['POST'])
def user_delete(user_id):
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return redirect(url_for('user_list'))

# --- Routes cho Quản lý Phòng học ---

# Danh sách Phòng học
@app.route('/rooms')
def room_list():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms").fetchall()
    return render_template('room_list.html', rooms=rooms, role=session['role'])

# Chi tiết Phòng học
@app.route('/rooms/<int:room_id>')
def room_detail(room_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if room:
        return render_template('room_detail.html', room=room, role=session['role'])
    return "Room not found", 404

# Tạo Phòng học mới (chỉ Admin)
@app.route('/rooms/create', methods=['GET', 'POST'])
def room_create():
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    if request.method == 'POST':
        room_data = request.form
        db = get_db()
        db.execute("INSERT INTO rooms (name, location, open_time, capacity) VALUES (?, ?, ?, ?)",
                   (room_data['name'], room_data['location'], room_data['open_time'], room_data['capacity']))
        db.commit()
        return redirect(url_for('room_list'))
    return render_template('room_edit.html', room=None, role=session['role'])

# Sửa Phòng học (chỉ Admin)
@app.route('/rooms/edit/<int:room_id>', methods=['GET', 'POST'])
def room_edit(room_id):
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        return "Room not found", 404

    if request.method == 'POST':
        room_data = request.form
        db.execute("UPDATE rooms SET name=?, location=?, open_time=?, capacity=? WHERE id=?",
                   (room_data['name'], room_data['location'], room_data['open_time'], room_data['capacity'], room_id))
        db.commit()
        return redirect(url_for('room_list'))

    return render_template('room_edit.html', room=room, role=session['role'])

# Xóa Phòng học (chỉ Admin)
@app.route('/rooms/delete/<int:room_id>', methods=['POST'])
def room_delete(room_id):
    if not session.get('logged_in') or session['role'] != 'admin':
        return "Permission Denied", 403
    db = get_db()
    db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    db.commit()
    return redirect(url_for('room_list'))

# Đăng xuất
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('role', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)