from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import session
from flask import flash
from datetime import date, datetime, timedelta
import mysql.connector
import connect


####### Required for the reset function to work both locally and in PythonAnywhere
from pathlib import Path

app = Flask(__name__)
app.secret_key = 'COMP636 S2'

start_date = datetime(2024, 10, 29)
pasture_growth_rate = 65    # kg DM/ha/day
stock_consumption_rate = 14 # kg DM/animal/day

db_connection = None

def initialize_db():
    """Initialize the database connection."""
    global db_connection
    if db_connection is None:
        db_connection = mysql.connector.connect(
            user=connect.dbuser,
            password=connect.dbpass,
            host=connect.dbhost,
            port=3306,
            database=connect.dbname,
            autocommit=True
        )

def getCursor():
    """Gets a new dictionary cursor for the database."""
    global db_connection
    if not db_connection.is_connected():
        initialize_db()
    cursor = db_connection.cursor(dictionary=True)
    return cursor

# 初始化数据库连接
initialize_db()

def get_date():
    """Reads the date from the database table."""
    cursor = getCursor()
    cursor.execute("SELECT curr_date FROM curr_date")
    result = cursor.fetchone()
    return result['curr_date'].isoformat() if result else None

def update_pasture(cursor, paddock_id, area, dm_per_ha):
    """Updates pasture values for a given paddock."""
    total_dm = area * dm_per_ha
    cursor.execute("UPDATE paddocks SET total_dm = %s, dm_per_ha = %s WHERE id = %s", (total_dm, dm_per_ha, paddock_id))

@app.route('/')
def home():
    session['curr_date'] = get_date()
    return render_template('home.html')

@app.route("/reset")
def reset():
    """Reset data to original state."""
    THIS_FOLDER = Path(__file__).parent.resolve()
    with open(THIS_FOLDER / 'fms-reset.sql', 'r') as f:
        mqstr = f.read()
        for qstr in mqstr.split(";"):
            if qstr.strip():
                cursor = getCursor()
                cursor.execute(qstr)
    session['curr_date'] = get_date()
    return redirect(url_for('paddocks'))

@app.route('/mobs')
def mobs():
    session['curr_date'] = get_date()
    cursor = getCursor()
    cursor.execute("""
        SELECT m.id, m.name, p.name AS paddock, COUNT(s.id) AS num_stock, AVG(s.weight) AS avg_weight 
        FROM mobs m 
        JOIN paddocks p ON m.paddock_id = p.id 
        LEFT JOIN stock s ON m.id = s.mob_id 
        GROUP BY m.id, m.name, p.name
    """)
    mobs = cursor.fetchall()
    return render_template('mobs.html', mobs=mobs)

@app.route('/paddocks')
def paddocks():
    session['curr_date'] = get_date()
    cursor = getCursor()
    cursor.execute("SELECT * FROM paddocks")
    paddocks = cursor.fetchall()
    return render_template('paddocks.html', paddocks=paddocks)

@app.route('/stock')
def stock():
    session['curr_date'] = get_date()
    cursor = getCursor()
    cursor.execute("""
        SELECT m.name, p.name AS paddock, COUNT(s.id) AS num_stock, AVG(s.weight) AS avg_weight, 
               GROUP_CONCAT(CONCAT(s.id, ': ', TIMESTAMPDIFF(YEAR, s.dob, CURDATE()))) AS animals
        FROM mobs m
        JOIN paddocks p ON m.paddock_id = p.id
        LEFT JOIN stock s ON m.id = s.mob_id
        GROUP BY m.name, p.name
    """)
    mobs = cursor.fetchall()
    return render_template('stock.html', mobs=mobs)

@app.route('/move_mob', methods=['GET', 'POST'])
def move_mob():
    if request.method == 'POST':
        mob_id = request.form.get('mob_id')
        new_paddock_id = request.form.get('new_paddock_id')
        
        cursor = getCursor()
        cursor.execute("SELECT id FROM mobs WHERE paddock_id = %s", (new_paddock_id,))
        existing_mob = cursor.fetchone()
        
        if existing_mob:
            flash('The selected paddock already contains a mob.', 'error')
            return redirect(url_for('paddocks'))
        
        try:
            cursor.execute("UPDATE mobs SET paddock_id = %s WHERE id = %s", (new_paddock_id, mob_id))
        except Exception as e:
            flash(f'An error occurred while moving the mob: {e}', 'error')
            return redirect(url_for('paddocks'))
        return redirect(url_for('paddocks'))
    else:
        cursor = getCursor()
        cursor.execute("SELECT id, name FROM mobs")
        mobs = cursor.fetchall()
        cursor.execute("SELECT id, name FROM paddocks")
        paddocks = cursor.fetchall()
        return render_template('move_mobs.html', mobs=mobs, paddocks=paddocks)

@app.route('/edit_paddocks', methods=['GET', 'POST'])
def edit_paddocks():
    if request.method == 'POST':
        try:
            for paddock in request.form:
                if paddock.startswith('area_'):
                    paddock_id = int(paddock.replace('area_', ''))
                    new_area = request.form[paddock]
                    cursor = getCursor()
                    cursor.execute("UPDATE paddocks SET area = %s WHERE id = %s", (new_area, paddock_id))
                    
            new_paddock_name = request.form.get('new_paddock_name')
            new_area = request.form.get('new_area')
            new_dm_per_ha = request.form.get('new_dm_per_ha')
            
            if new_paddock_name and new_area and new_dm_per_ha:
                cursor.execute("INSERT INTO paddocks (name, area, dm_per_ha) VALUES (%s, %s, %s)", 
                               (new_paddock_name, new_area, new_dm_per_ha))
        except Exception as e:
            flash(f'An error occurred while updating paddocks: {e}', 'error')
            return redirect(url_for('paddocks'))
        return redirect(url_for('paddocks'))
    else:
        cursor = getCursor()
        cursor.execute("SELECT * FROM paddocks")
        paddocks = cursor.fetchall()
        return render_template('edit_paddocks.html', paddocks=paddocks)

@app.route('/advance_date', methods=['POST'])
def advance_date():
    session['curr_date'] = (datetime.strptime(session['curr_date'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    cursor = getCursor()
    cursor.execute("SELECT p.id, p.area, COUNT(s.id) AS num_stock FROM paddocks p LEFT JOIN mobs m ON p.id = m.paddock_id LEFT JOIN stock s ON m.id = s.mob_id GROUP BY p.id")
    paddocks = cursor.fetchall()
    
    for paddock in paddocks:
        growth = paddock['area'] * pasture_growth_rate
        consumption = paddock['num_stock'] * stock_consumption_rate if paddock['num_stock'] else 0
        cursor.execute("SELECT dm_per_ha FROM paddocks WHERE id = %s", (paddock['id'], ))
        dm_per_ha = cursor.fetchone()['dm_per_ha']
        new_dm_per_ha = dm_per_ha + growth - consumption
        update_pasture(cursor, paddock['id'], paddock['area'], new_dm_per_ha)
    
    flash('Date advanced to the next day.', 'info')
    return redirect(url_for('paddocks'))

@app.route('/test_db')
def test_db():
    cursor = getCursor()
    cursor.execute("SELECT VERSION()")
    result = cursor.fetchone()
    return f"Database Version: {result['VERSION()']}"

@app.route('/edit_animal/<int:animal_id>', methods=['GET', 'POST'])
def edit_animal(animal_id):
    if request.method == 'POST':
        # 更新动物信息的逻辑
        weight = request.form.get('weight')
        dob = request.form.get('dob')
        cursor = getCursor()
        cursor.execute("UPDATE stock SET weight = %s, dob = %s WHERE id = %s", (weight, dob, animal_id))
        flash('Animal updated successfully.', 'success')
        return redirect(url_for('stock'))
    else:
        cursor = getCursor()
        cursor.execute("SELECT * FROM stock WHERE id = %s", (animal_id,))
        animal = cursor.fetchone()
        return render_template('edit_animal.html', animal=animal)

@app.route('/edit_paddock/<int:paddock_id>', methods=['GET', 'POST'])
def edit_paddock(paddock_id):
    if request.method == 'POST':
        # 更新围栏信息的逻辑
        name = request.form.get('name')
        area = request.form.get('area')
        dm_per_ha = request.form.get('dm_per_ha')
        cursor = getCursor()
        cursor.execute("UPDATE paddocks SET name = %s, area = %s, dm_per_ha = %s WHERE id = %s", (name, area, dm_per_ha, paddock_id))
        flash('Paddock updated successfully.', 'success')
        return redirect(url_for('paddocks'))
    else:
        cursor = getCursor()
        cursor.execute("SELECT * FROM paddocks WHERE id = %s", (paddock_id,))
        paddock = cursor.fetchone()
        return render_template('edit_paddock.html', paddock=paddock)

if __name__ == '__main__':
    app.run(debug=True)