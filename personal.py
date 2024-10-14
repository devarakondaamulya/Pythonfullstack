import sqlite3
from getpass import getpass
import hashlib
import os
import shutil
import datetime
import sys
import unittest

DATABASE = 'finance_manager.db'
BACKUP_DIR = 'backups'

# ----------------------------- Database Setup -----------------------------

def initialize_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Budgets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, category)
        )
    ''')
    
    conn.commit()
    conn.close()

# --------------------------- User Authentication --------------------------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user():
    username = input("Enter a unique username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    password = getpass("Enter your password: ").strip()
    if not password:
        print("Password cannot be empty.")
        return
    password_confirm = getpass("Confirm your password: ").strip()
    if password != password_confirm:
        print("Passwords do not match.")
        return
    password_hash = hash_password(password)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        print("User registered successfully!")
    except sqlite3.IntegrityError:
        print("Username already exists!")
    finally:
        conn.close()

def login_user():
    username = input("Username: ").strip()
    password = getpass("Password: ").strip()
    password_hash = hash_password(password)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?', (username, password_hash))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        print("Login successful!")
        return user[0]  # Return user_id
    else:
        print("Login failed! Please check your credentials.")
        return None

# ------------------------ Income and Expense Tracking ----------------------

def initialize_transactions_db():
    # Already handled in initialize_db
    pass

def add_transaction(user_id):
    type = input("Enter transaction type (income/expense): ").strip().lower()
    if type not in ['income', 'expense']:
        print("Invalid transaction type.")
        return
    category = input("Enter category (e.g., Food, Rent, Salary, etc.): ").strip()
    if not category:
        print("Category cannot be empty.")
        return
    try:
        amount = float(input("Enter amount: ").strip())
        if amount <= 0:
            print("Amount must be positive.")
            return
    except ValueError:
        print("Invalid amount.")
        return
    date = input("Enter date (YYYY-MM-DD) or leave blank for today: ").strip()
    if not date:
        date = datetime.date.today().isoformat()
    else:
        try:
            datetime.datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (user_id, type, category, amount, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, type, category, amount, date))
    conn.commit()
    conn.close()
    print(f"{type.capitalize()} of {amount} added successfully!")
    
    if type == 'expense':
        check_budget(user_id, category)

def view_transactions(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, type, category, amount, date FROM transactions WHERE user_id = ? ORDER BY date DESC', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    if not transactions:
        print("No transactions found.")
        return
    
    print("\nYour Transactions:")
    print("-" * 60)
    print(f"{'ID':<5} {'Type':<10} {'Category':<15} {'Amount':<10} {'Date':<10}")
    print("-" * 60)
    for txn in transactions:
        print(f"{txn[0]:<5} {txn[1]:<10} {txn[2]:<15} {txn[3]:<10.2f} {txn[4]:<10}")
    print("-" * 60)

def update_transaction(user_id):
    view_transactions(user_id)
    try:
        txn_id = int(input("Enter the ID of the transaction to update: ").strip())
    except ValueError:
        print("Invalid ID.")
        return
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT type, category, amount, date FROM transactions WHERE id = ? AND user_id = ?', (txn_id, user_id))
    txn = cursor.fetchone()
    if not txn:
        print("Transaction not found.")
        conn.close()
        return
    print("Leave field blank to keep current value.")
    new_type = input(f"Enter new type ({txn[0]}): ").strip().lower()
    if new_type and new_type not in ['income', 'expense']:
        print("Invalid transaction type.")
        conn.close()
        return
    new_category = input(f"Enter new category ({txn[1]}): ").strip()
    new_amount = input(f"Enter new amount ({txn[2]}): ").strip()
    new_date = input(f"Enter new date ({txn[3]}): ").strip()
    
    updated_type = new_type if new_type else txn[0]
    updated_category = new_category if new_category else txn[1]
    try:
        updated_amount = float(new_amount) if new_amount else txn[2]
        if updated_amount <= 0:
            print("Amount must be positive.")
            conn.close()
            return
    except ValueError:
        print("Invalid amount.")
        conn.close()
        return
    if new_date:
        try:
            datetime.datetime.strptime(new_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            conn.close()
            return
        updated_date = new_date
    else:
        updated_date = txn[3]
    
    cursor.execute('''
        UPDATE transactions
        SET type = ?, category = ?, amount = ?, date = ?
        WHERE id = ? AND user_id = ?
    ''', (updated_type, updated_category, updated_amount, updated_date, txn_id, user_id))
    conn.commit()
    conn.close()
    print("Transaction updated successfully!")
    
    if updated_type == 'expense':
        check_budget(user_id, updated_category)

def delete_transaction(user_id):
    view_transactions(user_id)
    try:
        txn_id = int(input("Enter the ID of the transaction to delete: ").strip())
    except ValueError:
        print("Invalid ID.")
        return
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT type, category FROM transactions WHERE id = ? AND user_id = ?', (txn_id, user_id))
    txn = cursor.fetchone()
    if not txn:
        print("Transaction not found.")
        conn.close()
        return
    confirm = input(f"Are you sure you want to delete this {txn[0]} in category {txn[1]}? (y/n): ").strip().lower()
    if confirm == 'y':
        cursor.execute('DELETE FROM transactions WHERE id = ? AND user_id = ?', (txn_id, user_id))
        conn.commit()
        print("Transaction deleted successfully!")
    else:
        print("Deletion cancelled.")
    conn.close()

# --------------------------- Financial Reporting --------------------------

def generate_report(user_id, period='monthly'):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    today = datetime.date.today()
    if period == 'monthly':
        period_str = today.strftime('%Y-%m')
        cursor.execute('''
            SELECT type, SUM(amount) FROM transactions 
            WHERE user_id = ? AND strftime('%Y-%m', date) = ? 
            GROUP BY type
        ''', (user_id, period_str))
    elif period == 'yearly':
        period_str = today.strftime('%Y')
        cursor.execute('''
            SELECT type, SUM(amount) FROM transactions 
            WHERE user_id = ? AND strftime('%Y', date) = ? 
            GROUP BY type
        ''', (user_id, period_str))
    else:
        print("Invalid period. Choose 'monthly' or 'yearly'.")
        conn.close()
        return
    
    report = cursor.fetchall()
    conn.close()
    
    total_income = total_expenses = 0
    for row in report:
        if row[0] == 'income':
            total_income = row[1]
        elif row[0] == 'expense':
            total_expenses = row[1]
    
    print(f"\n--- {period.capitalize()} Financial Report ({period_str}) ---")
    print(f"Total Income: {total_income:.2f}")
    print(f"Total Expenses: {total_expenses:.2f}")
    print(f"Savings: {total_income - total_expenses:.2f}\n")

def view_report_menu(user_id):
    while True:
        print("\n--- Financial Reports ---")
        print("1. Monthly Report")
        print("2. Yearly Report")
        print("3. Back to Main Menu")
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            generate_report(user_id, period='monthly')
        elif choice == '2':
            generate_report(user_id, period='yearly')
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

# ----------------------------- Budgeting -----------------------------------

def set_budget(user_id):
    category = input("Enter category to set budget for: ").strip()
    if not category:
        print("Category cannot be empty.")
        return
    try:
        amount = float(input("Enter budget amount: ").strip())
        if amount <= 0:
            print("Budget amount must be positive.")
            return
    except ValueError:
        print("Invalid amount.")
        return
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO budgets (user_id, category, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, category) DO UPDATE SET amount=excluded.amount
        ''', (user_id, category, amount))
        conn.commit()
        print(f"Budget for category '{category}' set to {amount:.2f}.")
    except sqlite3.Error as e:
        print("Error setting budget:", e)
    finally:
        conn.close()

def view_budgets(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT category, amount FROM budgets WHERE user_id = ?', (user_id,))
    budgets = cursor.fetchall()
    conn.close()
    
    if not budgets:
        print("No budgets set.")
        return
    
    print("\nYour Budgets:")
    print("-" * 30)
    print(f"{'Category':<15} {'Budget':<10}")
    print("-" * 30)
    for budget in budgets:
        print(f"{budget[0]:<15} {budget[1]:<10.2f}")
    print("-" * 30)

def check_budget(user_id, category):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT amount FROM budgets WHERE user_id = ? AND category = ?', (user_id, category))
    budget = cursor.fetchone()
    if not budget:
        conn.close()
        return  # No budget set for this category
    budget_amount = budget[0]
    
    cursor.execute('''
        SELECT SUM(amount) FROM transactions 
        WHERE user_id = ? AND type = 'expense' AND category = ?
    ''', (user_id, category))
    total_expense = cursor.fetchone()[0] or 0.0
    conn.close()
    
    if total_expense > budget_amount:
        print(f"Alert: You have exceeded your budget for '{category}'.")
    elif total_expense == budget_amount:
        print(f"Notice: You have reached your budget limit for '{category}'.")

def budgeting_menu(user_id):
    while True:
        print("\n--- Budgeting ---")
        print("1. Set Budget")
        print("2. View Budgets")
        print("3. Back to Main Menu")
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            set_budget(user_id)
        elif choice == '2':
            view_budgets(user_id)
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

# --------------------------- Data Persistence ------------------------------

def backup_data():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    backup_file = os.path.join(BACKUP_DIR, f'backup_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.db')
    shutil.copyfile(DATABASE, backup_file)
    print(f"Backup created at {backup_file}.")

def restore_data():
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')]
    if not backups:
        print("No backups available.")
        return
    print("\nAvailable Backups:")
    for idx, file in enumerate(backups, 1):
        print(f"{idx}. {file}")
    try:
        choice = int(input("Enter the number of the backup to restore: ").strip())
        if choice < 1 or choice > len(backups):
            print("Invalid choice.")
            return
        backup_file = os.path.join(BACKUP_DIR, backups[choice - 1])
        shutil.copyfile(backup_file, DATABASE)
        print(f"Data restored from {backup_file}.")
    except ValueError:
        print("Invalid input.")

def data_persistence_menu():
    while True:
        print("\n--- Data Persistence ---")
        print("1. Backup Data")
        print("2. Restore Data")
        print("3. Back to Main Menu")
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            backup_data()
        elif choice == '2':
            restore_data()
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

# ------------------------- Main Application Flow --------------------------

def main_menu(user_id):
    while True:
        print("\n--- Personal Finance Management ---")
        print("1. Add Transaction")
        print("2. View Transactions")
        print("3. Update Transaction")
        print("4. Delete Transaction")
        print("5. Financial Reports")
        print("6. Budgeting")
        print("7. Data Backup/Restore")
        print("8. Logout")
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            add_transaction(user_id)
        elif choice == '2':
            view_transactions(user_id)
        elif choice == '3':
            update_transaction(user_id)
        elif choice == '4':
            delete_transaction(user_id)
        elif choice == '5':
            view_report_menu(user_id)
        elif choice == '6':
            budgeting_menu(user_id)
        elif choice == '7':
            data_persistence_menu()
        elif choice == '8':
            print("Logging out...")
            break
        else:
            print("Invalid choice. Please try again.")

def start_application():
    initialize_db()
    while True:
        print("\n--- Welcome to Personal Finance Manager ---")
        print("1. Register")
        print("2. Login")
        print("3. Exit")
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            register_user()
        elif choice == '2':
            user_id = login_user()
            if user_id:
                main_menu(user_id)
        elif choice == '3':
            print("Exiting application. Goodbye!")
            sys.exit()
        else:
            print("Invalid choice. Please try again.")

# ----------------------------- Unit Testing -------------------------------

class TestFinanceManager(unittest.TestCase):
    def setUp(self):
        # Setup a test database
        self.test_db = 'test_finance_manager.db'
        global DATABASE
        DATABASE = self.test_db
        initialize_db()
        self.conn = sqlite3.connect(self.test_db)
        self.cursor = self.conn.cursor()
        # Create a test user
        self.username = 'testuser'
        self.password = 'testpass'
        self.password_hash = hash_password(self.password)
        self.cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (self.username, self.password_hash))
        self.conn.commit()
        self.cursor.execute('SELECT id FROM users WHERE username = ?', (self.username,))
        self.user_id = self.cursor.fetchone()[0]
    
    def tearDown(self):
        self.conn.close()
        os.remove(self.test_db)
    
    def test_user_registration(self):
        # Attempt to register a new user
        with unittest.mock.patch('builtins.input', side_effect=['newuser']), \
             unittest.mock.patch('getpass.getpass', side_effect=['newpass', 'newpass']):
            register_user()
            self.cursor.execute('SELECT * FROM users WHERE username = ?', ('newuser',))
            user = self.cursor.fetchone()
            self.assertIsNotNone(user)
    
    def test_duplicate_user_registration(self):
        # Attempt to register an existing user
        with unittest.mock.patch('builtins.input', side_effect=[self.username]), \
             unittest.mock.patch('getpass.getpass', side_effect=['newpass', 'newpass']):
            with unittest.mock.patch('builtins.print') as mocked_print:
                register_user()
                mocked_print.assert_any_call("Username already exists!")
    
    def test_user_login_success(self):
        with unittest.mock.patch('builtins.input', side_effect=[self.username]), \
             unittest.mock.patch('getpass.getpass', side_effect=[self.password]):
            user_id = login_user()
            self.assertEqual(user_id, self.user_id)
    
    def test_user_login_failure(self):
        with unittest.mock.patch('builtins.input', side_effect=[self.username]), \
             unittest.mock.patch('getpass.getpass', side_effect=['wrongpass']):
            user_id = login_user()
            self.assertIsNone(user_id)
    
    def test_add_transaction(self):
        with unittest.mock.patch('builtins.input', side_effect=['income', 'Salary', '5000', '2024-10-11']):
            add_transaction(self.user_id)
            self.cursor.execute('SELECT * FROM transactions WHERE user_id = ?', (self.user_id,))
            txn = self.cursor.fetchone()
            self.assertIsNotNone(txn)
            self.assertEqual(txn[2], 'income')
            self.assertEqual(txn[3], 'Salary')
            self.assertEqual(txn[4], 5000.0)
            self.assertEqual(txn[5], '2024-10-11')
    
    def test_set_budget(self):
        with unittest.mock.patch('builtins.input', side_effect=['Food', '500']):
            set_budget(self.user_id)
            self.cursor.execute('SELECT * FROM budgets WHERE user_id = ? AND category = ?', (self.user_id, 'Food'))
            budget = self.cursor.fetchone()
            self.assertIsNotNone(budget)
            self.assertEqual(budget[2], 500.0)

# ----------------------------- Entry Point -------------------------------

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        unittest.main(argv=['first-arg-is-ignored'], exit=False)
    else:
        start_application()
