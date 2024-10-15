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

start_date = datetime(2024,10,29)
pasture_growth_rate = 65    #kg DM/ha/day
stock_consumption_rate = 14 #kg DM/animal/day

def getCursor():
    """Gets a new dictionary cursor for the database."""
    global db_connection
    
    if db_connection is None or not db_connection.is_connected():
        db_connection = mysql.connector.connect(
            user=connect.dbuser,
            password=connect.dbpass,
            host=connect.dbhost,
            database=connect.dbname,
            autocommit=True
        )
        
    cursor = db_connection.cursor(dictionary=True)
    return cursor

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

if __name__ == '__main__':
    app.run(debug=True)