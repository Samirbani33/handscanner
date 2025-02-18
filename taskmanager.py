import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime, timedelta
import os
from zoneinfo import ZoneInfo
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class TaskManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mechanic Shop Task Manager")
        self.root.geometry("1000x700")

        # Set timezone for Toronto
        self.timezone = ZoneInfo("America/Toronto")
        
        # Business hours in 12-hour format with leading zeros to match database
        self.business_hours = [
            '08:00 AM',
            '09:00 AM',
            '10:00 AM',
            '11:00 AM',
            '12:00 PM',
            '01:00 PM',
            '02:00 PM',
            '03:00 PM',
            '04:00 PM',
            '05:00 PM',
            '06:00 PM',
            '07:00 PM'
        ]
        
        # Initialize database first
        self.init_database()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create tabs
        self.schedule_tab = ttk.Frame(self.notebook)
        self.weekly_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.schedule_tab, text='Schedule Appointment')
        self.notebook.add(self.weekly_tab, text='Weekly View')
        
        # Initialize current week BEFORE creating GUI
        today = datetime.now(self.timezone)
        self.current_week_start = today - timedelta(days=today.weekday())
        
        # Create GUI elements
        self.create_schedule_gui()
        self.create_weekly_gui()
        
        # Start time updates
        self.update_time()

    def update_time(self):
        """Update current time display"""
        current_time = datetime.now(self.timezone)
        time_str = current_time.strftime('%I:%M %p ET - %A, %B %d, %Y')
        self.time_label.config(text=time_str)
        self.root.after(60000, self.update_time)  # Update every minute

    def init_database(self):
        db_path = resource_path('mechanic_appointments.db')
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create appointments table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                reason TEXT NOT NULL,
                appointment_date TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create repair_reasons table to store unique reasons
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS repair_reasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT UNIQUE NOT NULL
            )
        ''')
        
        self.conn.commit()
        
        # Clean old appointments automatically
        self.clean_old_appointments()

    def clean_old_appointments(self):
        """Clean appointments older than 2 weeks but save unique reasons"""
        try:
            # Get current date in the shop's timezone
            current_date = datetime.now(self.timezone)
            two_weeks_ago = (current_date - timedelta(days=14)).strftime('%Y-%m-%d')
            
            # First, save any unique reasons to repair_reasons table
            self.cursor.execute('''
                INSERT OR IGNORE INTO repair_reasons (reason)
                SELECT DISTINCT reason FROM appointments 
                WHERE appointment_date < ?
            ''', (two_weeks_ago,))
            
            # Then delete old appointments
            self.cursor.execute('''
                DELETE FROM appointments 
                WHERE appointment_date < ?
            ''', (two_weeks_ago,))
            
            self.conn.commit()
            print(f"Cleaned appointments older than {two_weeks_ago}")
        except Exception as e:
            print(f"Error cleaning appointments: {e}")

    def create_schedule_gui(self):
        # Time display
        self.time_label = ttk.Label(self.schedule_tab, font=('Arial', 12))
        self.time_label.pack(pady=5)

        # Customer Information Frame
        info_frame = ttk.LabelFrame(self.schedule_tab, text="Customer Information", padding="10")
        info_frame.pack(fill='x', padx=10, pady=5)

        # Grid for customer info
        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_entry = ttk.Entry(info_frame, width=30)
        self.name_entry.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(info_frame, text="Phone Number:").grid(row=1, column=0, sticky="w")
        self.phone_entry = ttk.Entry(info_frame, width=30)
        self.phone_entry.grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(info_frame, text="Reason:").grid(row=2, column=0, sticky="w")
        self.reason_entry = ttk.Combobox(info_frame, width=27)
        self.reason_entry.grid(row=2, column=1, padx=5, pady=2)
        self.update_reason_dropdown()

        ttk.Label(info_frame, text="Date (YYYY-MM-DD):").grid(row=3, column=0, sticky="w")
        self.date_entry = ttk.Entry(info_frame, width=30)
        self.date_entry.grid(row=3, column=1, padx=5, pady=2)
        self.date_entry.insert(0, datetime.now(self.timezone).strftime('%Y-%m-%d'))

        ttk.Label(info_frame, text="Time:").grid(row=4, column=0, sticky="w")
        self.time_entry = ttk.Combobox(info_frame, width=27, values=self.business_hours)
        self.time_entry.grid(row=4, column=1, padx=5, pady=2)
        self.time_entry.set(self.business_hours[0])

        ttk.Button(info_frame, text="Set Appointment", command=self.add_appointment).grid(row=5, column=0, columnspan=2, pady=10)

        # Appointments Display
        self.tree = ttk.Treeview(self.schedule_tab, columns=('Name', 'Phone', 'Reason', 'Date', 'Time'), show='headings')
        self.tree.pack(fill='both', expand=True, padx=10, pady=5)

        for col in ['Name', 'Phone', 'Reason', 'Date', 'Time']:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        self.refresh_appointments()

        # Add Edit and Delete buttons
        button_frame = ttk.Frame(self.schedule_tab)
        button_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_appointment).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_appointment).pack(side='left', padx=5)

        # Bind double-click on appointment to edit
        self.tree.bind('<Double-1>', lambda e: self.edit_appointment())

        # Adjust column widths in the main appointment list
        self.tree.column('Name', width=150)
        self.tree.column('Phone', width=120)
        self.tree.column('Reason', width=300)  # Increased width for longer reasons
        self.tree.column('Date', width=100)
        self.tree.column('Time', width=100)

        # Add horizontal scrollbar
        xscroll = ttk.Scrollbar(self.schedule_tab, orient='horizontal', command=self.tree.xview)
        xscroll.pack(fill='x', side='bottom')
        self.tree.configure(xscrollcommand=xscroll.set)

    def format_time_for_db(self, time_str):
        """Convert any time format to consistent database format"""
        try:
            # Handle different possible input formats
            if ':' in time_str:
                if 'AM' in time_str.upper() or 'PM' in time_str.upper():
                    # Ensure consistent format with leading zeros
                    time_obj = datetime.strptime(time_str, '%I:%M %p')
                    return time_obj.strftime('%I:%M %p')
                else:
                    # Convert 24-hour format to 12-hour
                    time_obj = datetime.strptime(time_str, '%H:%M')
                    return time_obj.strftime('%I:%M %p')
            return time_str
        except ValueError:
            return time_str

    def format_time_for_display(self, time_str):
        """Ensure consistent time display format"""
        try:
            # If time is in 24-hour format, convert to 12-hour
            if ':' in time_str:
                if 'AM' in time_str.upper() or 'PM' in time_str.upper():
                    # Already in 12-hour format
                    time_obj = datetime.strptime(time_str, '%I:%M %p')
                else:
                    # Convert from 24-hour format
                    time_obj = datetime.strptime(time_str, '%H:%M')
                return time_obj.strftime('%I:%M %p')
            return time_str
        except ValueError:
            return time_str

    def add_appointment(self):
        name = self.name_entry.get()
        phone = self.phone_entry.get()
        reason = self.reason_entry.get()
        date = self.date_entry.get()
        time = self.time_entry.get()

        if name and phone and reason and date and time:
            # Validate that the selected day is not a Sunday
            selected_date = datetime.strptime(date, '%Y-%m-%d')
            if selected_date.weekday() == 6:  # Sunday
                messagebox.showerror("Error", "Shop is closed on Sundays. Please select another day.")
                return

            # Format time consistently
            formatted_time = self.format_time_for_db(time)
            
            self.cursor.execute('''
                INSERT INTO appointments (customer_name, phone_number, reason, appointment_date, appointment_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, phone, reason, date, formatted_time))
            self.conn.commit()
            
            # Clear entries
            self.name_entry.delete(0, tk.END)
            self.phone_entry.delete(0, tk.END)
            self.reason_entry.set('')
            self.time_entry.set(self.business_hours[0])
            
            self.refresh_appointments()
            self.update_reason_dropdown()
            self.update_weekly_view()

    def search_appointments(self, event=None):
        search_term = self.search_entry.get()
        
        # Clear the treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Search the database
        self.cursor.execute('''
            SELECT customer_name, phone_number, reason, appointment_date, appointment_time 
            FROM appointments 
            WHERE reason LIKE ?
        ''', ('%' + search_term + '%',))
        
        for row in self.cursor.fetchall():
            self.tree.insert('', tk.END, values=row)

    def refresh_appointments(self):
        # Clear the treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Fetch all appointments
        self.cursor.execute('''
            SELECT customer_name, phone_number, reason, appointment_date, appointment_time 
            FROM appointments 
            ORDER BY appointment_date DESC, appointment_time ASC
            LIMIT 1000
        ''')
        
        for row in self.cursor.fetchall():
            self.tree.insert('', tk.END, values=row)

    def create_weekly_gui(self):
        """Create the weekly view interface"""
        # Weekly view frame
        self.weekly_frame = ttk.Frame(self.weekly_tab)
        self.weekly_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Navigation frame at top
        nav_frame = ttk.Frame(self.weekly_frame)
        nav_frame.pack(fill='x', pady=5)
        
        ttk.Button(nav_frame, text="Previous Week", command=self.prev_week).pack(side='left', padx=5)
        self.week_label = ttk.Label(nav_frame, text="", font=('Arial', 10))
        self.week_label.pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Next Week", command=self.next_week).pack(side='left', padx=5)

        # Create main grid frame
        self.time_frame = ttk.Frame(self.weekly_frame)
        self.time_frame.pack(fill='both', expand=True, pady=5)

        # Days of the week (Monday to Saturday)
        days = ['Time', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        for i, day in enumerate(days):
            ttk.Label(self.time_frame, text=day, font=('Arial', 10, 'bold')).grid(
                row=0, column=i, padx=2, pady=5, sticky='nsew'
            )
            if i > 0:  # Skip time column
                self.time_frame.grid_columnconfigure(i, weight=1, minsize=150)

        # Time slots
        for i, time in enumerate(self.business_hours, 1):
            # Time column
            ttk.Label(self.time_frame, text=time, width=10).grid(
                row=i, column=0, padx=2, pady=2, sticky='w'
            )
            
            # Appointment slots
            for j in range(1, 7):  # Monday to Saturday
                frame = ttk.Frame(self.time_frame, relief='solid', borderwidth=1)
                frame.grid(row=i, column=j, padx=2, pady=2, sticky='nsew')
                label = ttk.Label(frame, wraplength=150, justify='left')
                label.pack(padx=5, pady=5, fill='both', expand=True)

        # Configure grid
        self.time_frame.grid_columnconfigure(0, minsize=100)  # Time column width
        for i in range(len(self.business_hours) + 1):
            self.time_frame.grid_rowconfigure(i, weight=1)

    def update_weekly_view(self):
        """Update the weekly view with appointments"""
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.config(text=f"Week of {self.current_week_start.strftime('%B %d')} to {week_end.strftime('%B %d, %Y')}")

        # Clear existing appointments
        for widget in self.time_frame.winfo_children():
            if isinstance(widget, ttk.Frame):
                for label in widget.winfo_children():
                    label.config(text='')

        # Get appointments for the week - added phone_number to SELECT
        self.cursor.execute('''
            SELECT customer_name, phone_number, reason, appointment_date, appointment_time
            FROM appointments
            WHERE appointment_date BETWEEN ? AND ?
            ORDER BY appointment_date, appointment_time
        ''', (self.current_week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
        
        appointments = self.cursor.fetchall()
        print(f"Found appointments: {appointments}")

        # Update the weekly view with appointments
        for appt in appointments:
            try:
                date = datetime.strptime(appt[3], '%Y-%m-%d')  # Index changed due to added phone
                day_index = date.weekday()
                
                if day_index < 6:  # Skip Sunday (6)
                    time_slot = appt[4]  # Index changed due to added phone
                    # Ensure time slot has leading zeros
                    if len(time_slot.split(':')[0]) == 1:
                        hour = time_slot.split(':')[0]
                        time_slot = f"0{time_slot}"
                    
                    time_index = self.business_hours.index(time_slot)
                    
                    # Find the frame and update its label
                    for widget in self.time_frame.grid_slaves(row=time_index + 1, column=day_index + 1):
                        if isinstance(widget, ttk.Frame):
                            label = widget.winfo_children()[0]
                            # Format: Name, Phone, and Reason
                            label.config(text=f"{appt[0]}\n{appt[1]}\n{appt[2]}")
                            print(f"Updated cell for {appt[0]} at {time_slot} on {date}")
                            break
                            
            except Exception as e:
                print(f"Error displaying appointment: {e}, Appointment: {appt}")

    def update_reason_dropdown(self):
        """Update dropdown with reasons from both tables"""
        self.cursor.execute('''
            SELECT DISTINCT reason FROM (
                SELECT reason FROM appointments
                UNION
                SELECT reason FROM repair_reasons
            )
            ORDER BY reason
        ''')
        reasons = [row[0] for row in self.cursor.fetchall()]
        self.reason_entry['values'] = reasons
        if reasons:
            self.reason_entry.set('')

    def prev_week(self):
        """Navigate to previous week"""
        self.current_week_start -= timedelta(days=7)
        self.update_weekly_view()
        print(f"Moved to week starting {self.current_week_start.strftime('%Y-%m-%d')}")

    def next_week(self):
        """Navigate to next week"""
        self.current_week_start += timedelta(days=7)
        self.update_weekly_view()
        print(f"Moved to week starting {self.current_week_start.strftime('%Y-%m-%d')}")

    def edit_appointment(self):
        """Edit selected appointment"""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an appointment to edit")
            return

        # Get current values
        current_values = self.tree.item(selected_item[0])['values']
        
        # Create edit window
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Appointment")
        edit_window.geometry("400x300")

        # Add fields
        ttk.Label(edit_window, text="Name:").pack(pady=5)
        name_entry = ttk.Entry(edit_window)
        name_entry.insert(0, current_values[0])
        name_entry.pack(pady=5)

        ttk.Label(edit_window, text="Phone:").pack(pady=5)
        phone_entry = ttk.Entry(edit_window)
        phone_entry.insert(0, current_values[1])
        phone_entry.pack(pady=5)

        ttk.Label(edit_window, text="Reason:").pack(pady=5)
        reason_entry = ttk.Combobox(edit_window, values=self.reason_entry['values'])
        reason_entry.set(current_values[2])
        reason_entry.pack(pady=5)

        ttk.Label(edit_window, text="Date (YYYY-MM-DD):").pack(pady=5)
        date_entry = ttk.Entry(edit_window)
        date_entry.insert(0, current_values[3])
        date_entry.pack(pady=5)

        ttk.Label(edit_window, text="Time:").pack(pady=5)
        time_entry = ttk.Combobox(edit_window, values=self.business_hours)
        time_entry.set(current_values[4])
        time_entry.pack(pady=5)

        def save_changes():
            # Update database
            self.cursor.execute('''
                UPDATE appointments 
                SET customer_name=?, phone_number=?, reason=?, appointment_date=?, appointment_time=?
                WHERE customer_name=? AND appointment_date=? AND appointment_time=?
            ''', (
                name_entry.get(), phone_entry.get(), reason_entry.get(),
                date_entry.get(), time_entry.get(),
                current_values[0], current_values[3], current_values[4]
            ))
            self.conn.commit()
            
            # Refresh views
            self.refresh_appointments()
            self.update_weekly_view()
            edit_window.destroy()

        ttk.Button(edit_window, text="Save Changes", command=save_changes).pack(pady=20)

    def delete_appointment(self):
        """Delete selected appointment"""
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select an appointment to delete")
            return

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this appointment?"):
            values = self.tree.item(selected_item[0])['values']
            self.cursor.execute('''
                DELETE FROM appointments 
                WHERE customer_name=? AND appointment_date=? AND appointment_time=?
            ''', (values[0], values[3], values[4]))
            self.conn.commit()
            
            # Refresh views
            self.refresh_appointments()
            self.update_weekly_view()

    def run(self):
        # Clean old appointments every time the app starts
        self.clean_old_appointments()
        self.root.mainloop()

if __name__ == "__main__":
    app = TaskManager()
    app.run()

