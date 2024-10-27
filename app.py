from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import mysql.connector
import connect
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
    if db_connection is None or not db_connection.is_connected():
        initialize_db()
    cursor = db_connection.cursor(dictionary=True)
    return cursor


# Initialize database connection
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
    # Set the current date to the session
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
    # Update the current date after reset
    session['curr_date'] = get_date()
    return redirect(url_for('paddocks'))

@app.route('/mobs')
def mobs():
    # Set the current date to the session
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
    # Set the current date to the session
    session['curr_date'] = get_date()
    cursor = getCursor()
    cursor.execute("SELECT * FROM paddocks")
    paddocks = cursor.fetchall()
    return render_template('paddocks.html', paddocks=paddocks)

@app.route('/stock')
def stock():
    # Set the current date to the session
    session['curr_date'] = get_date()
    cursor = getCursor()
    
    # Get basic information about each mob
    cursor.execute("""
        SELECT m.id, m.name, p.name AS paddock, COUNT(s.id) AS num_stock, AVG(s.weight) AS avg_weight 
        FROM mobs m 
        JOIN paddocks p ON m.paddock_id = p.id 
        LEFT JOIN stock s ON m.id = s.mob_id 
        GROUP BY m.id, m.name, p.name
    """)
    mobs_info = cursor.fetchall()
    
    # Get all animals within each mob
    for mob in mobs_info:
        cursor.execute("SELECT id, dob, weight FROM stock WHERE mob_id = %s", (mob['id'],))
        mob['animals'] = cursor.fetchall()
        for animal in mob['animals']:
            # Calculate age using session['curr_date']
            curr_date = datetime.strptime(session['curr_date'], '%Y-%m-%d').date()
            animal['age'] = (curr_date - animal['dob']).days // 365
    
    return render_template('stock.html', mobs=mobs_info)

@app.route('/move_mob', methods=['GET', 'POST'])
def move_mob():
    if request.method == 'POST':
        # Process the move mob form submission
        mob_id = request.form.get('mob_id')
        new_paddock_id = request.form.get('new_paddock_id')
        
        cursor = getCursor()
        cursor.execute("SELECT id FROM mobs WHERE paddock_id = %s", (new_paddock_id,))
        existing_mob = cursor.fetchone()
        
        if existing_mob:
            # Flash an error if the paddock already contains a mob
            flash('The selected paddock already contains a mob.', 'error')
            return redirect(url_for('paddocks'))
        
        try:
            cursor.execute("UPDATE mobs SET paddock_id = %s WHERE id = %s", (new_paddock_id, mob_id))
        except mysql.connector.Error as e:
            # Flash an error if there was a problem moving the mob
            flash(f'An error occurred while moving the mob: {e}', 'error')
            return redirect(url_for('paddocks'))
        return redirect(url_for('paddocks'))
    else:
        # GET request to show the move mob form
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
            # Update areas of existing paddocks
            for paddock in request.form:
                if paddock.startswith('area_'):
                    paddock_id = int(paddock.replace('area_', ''))
                    new_area = request.form[paddock]
                    cursor = getCursor()
                    cursor.execute("UPDATE paddocks SET area = %s WHERE id = %s", (new_area, paddock_id))
            
            # Insert a new paddock if all fields are filled
            new_paddock_name = request.form.get('new_paddock_name')
            new_area = request.form.get('new_area')
            new_dm_per_ha = request.form.get('new_dm_per_ha')
            
            if new_paddock_name and new_area and new_dm_per_ha:
                cursor.execute("INSERT INTO paddocks (name, area, dm_per_ha) VALUES (%s, %s, %s)", 
                               (new_paddock_name, new_area, new_dm_per_ha))
        except Exception as e:
            # Flash an error if there was a problem updating paddocks
            flash(f'An error occurred while updating paddocks: {e}', 'error')
            return redirect(url_for('paddocks'))
        return redirect(url_for('paddocks'))
    else:
        # GET request to show the edit paddocks form
        cursor = getCursor()
        cursor.execute("SELECT * FROM paddocks ORDER BY name")
        paddocks = cursor.fetchall()
        return render_template('edit_paddocks.html', paddocks=paddocks)

@app.route('/advance_date', methods=['POST'])
def advance_date():
    # Advance the date by one day
    session['curr_date'] = (datetime.strptime(session['curr_date'], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    
    cursor = getCursor()
    cursor.execute("SELECT p.id, p.area, COUNT(s.id) AS num_stock FROM paddocks p LEFT JOIN mobs m ON p.id = m.paddock_id LEFT JOIN stock s ON m.id = s.mob_id GROUP BY p.id")
    paddocks = cursor.fetchall()
    
    for paddock in paddocks:
        # Calculate growth and consumption
        growth = paddock['area'] * pasture_growth_rate
        consumption = paddock['num_stock'] * stock_consumption_rate if paddock['num_stock'] else 0
        cursor.execute("SELECT dm_per_ha FROM paddocks WHERE id = %s", (paddock['id'], ))
        dm_per_ha = cursor.fetchone()['dm_per_ha']
        new_dm_per_ha = max(dm_per_ha + growth - consumption, 0)
        update_pasture(cursor, paddock['id'], paddock['area'], new_dm_per_ha)
    
    # Flash a message after advancing the date
    flash('Date advanced to the next day.', 'info')
    return redirect(url_for('paddocks'))

@app.route('/test_db')
def test_db():
    # Test the database connection
    cursor = getCursor()
    cursor.execute("SELECT VERSION()")
    result = cursor.fetchone()
    return f"Database Version: {result['VERSION()']}"

@app.route('/edit_animal/<int:animal_id>')
def edit_animal(animal_id):
    # Retrieve an animal's details for editing
    cursor = getCursor()
    cursor.execute("SELECT * FROM stock WHERE id = %s", (animal_id,))
    animal = cursor.fetchone()

    if animal is None:
        return "Animal not found"

    return render_template('edit_animal.html', animal=animal)

# Route for updating animal information
@app.route('/update_animal/<int:animal_id>', methods=['POST'])
def update_animal(animal_id):
    cursor = getCursor()
    data = request.form
    cursor.execute(
        "UPDATE stock SET dob = %s, weight = %s WHERE id = %s",
        (data['dob'], data['weight'], animal_id)
    )
    return redirect(url_for('stock'))

@app.route('/update_paddock/<int:paddock_id>', methods=['POST'])
def update_paddock(paddock_id):
    # Update paddock's area and DM/ha
    new_area = request.form.get('new_area')
    new_dm_per_ha = request.form.get('new_dm_per_ha')

    try:
        new_area = float(new_area)
        new_dm_per_ha = float(new_dm_per_ha)
    except ValueError:
        # Flash an error if the input is invalid
        flash('Area and DM/ha must be numbers.', 'error')
        return redirect(url_for('edit_paddocks'))

    cursor = getCursor()
    cursor.execute("UPDATE paddocks SET area = %s, dm_per_ha = %s WHERE id = %s", (new_area, new_dm_per_ha, paddock_id))
    # Flash a success message
    flash('Paddock updated successfully.', 'success')
    return redirect(url_for('edit_paddocks'))

@app.before_request
def before_request():
    # Set the current date to the session if not set
    session.setdefault('curr_date', get_date())
    global db_connection
    if db_connection is not None and not db_connection.is_connected():
        initialize_db()

@app.teardown_request
def teardown_request(exception=None):
    global db_connection
    if db_connection is not None and db_connection.is_connected():
        db_connection.close()
        db_connection = None

if __name__ == '__main__':
    app.run(debug=True)