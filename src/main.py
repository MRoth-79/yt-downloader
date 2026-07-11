import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp
import os
import threading

def browse_folder():
    selected_dir = filedialog.askdirectory()
    if selected_dir:
        folder_var.set(selected_dir)

def download_worker(url, output_dir, format_type):
    """פונקציה שרצה בחוט נפרד ומבצעת את ההורדה בפועל"""
    # הגדרות בסיסיות ל-yt-dlp
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
    }

    # התאמת ההגדרות לפי הפורמט הנבחר
    if format_type == "MP3":
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else: # MP4
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # עדכון הממשק בסיום מוצלח (משתמשים ב-root.after כדי לחזור בבטחה ל-Main Thread)
        root.after(0, lambda: download_success(format_type))
    except Exception as e:
        # עדכון הממשק במקרה של שגיאה
        root.after(0, lambda: download_failed(str(e)))

def download_success(format_type):
    status_label.config(text="ההורדה הסתיימה בהצלחה!", fg="green")
    download_button.config(state=tk.NORMAL)
    messagebox.showinfo("הצלחה", f"הסרטון ירד כקובץ {format_type} בהצלחה!")

def download_failed(error_msg):
    status_label.config(text="ההורדה נכשלה", fg="red")
    download_button.config(state=tk.NORMAL)
    messagebox.showerror("שגיאה בהורדה", f"התרחשה שגיאה:\n{error_msg}")

def start_download():
    url = url_var.get().strip()
    output_dir = folder_var.get().strip()
    format_type = format_var.get()
    
    if not url:
        messagebox.showerror("שגיאה", "אנא הכנס קישור מיוטיוב")
        return
    if not output_dir or not os.path.exists(output_dir):
        messagebox.showerror("שגיאה", "אנא בחר תיקיית יעד תקינה")
        return

    # מניעת לחיצות כפולות בזמן ההורדה
    download_button.config(state=tk.DISABLED)
    status_label.config(text=f"מוריד {format_type}, אנא המתן...", fg="blue")
    
    # הפעלת תהליך ההורדה ב-Thread נפרד כדי למנוע את תקיעת ה-GUI
    threading.Thread(target=download_worker, args=(url, output_dir, format_type), daemon=True).start()

# עיצוב חלון ה-GUI
root = tk.Tk()
root.title("YouTube Media Downloader")
root.geometry("550x300")
root.resizable(False, False)

url_var = tk.StringVar()
folder_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
format_var = tk.StringVar(value="MP3")

# אלמנטים על המסך
tk.Label(root, text=":קישור לסרטון מיוטיוב", font=("Arial", 11)).pack(pady=5)
tk.Entry(root, textvariable=url_var, width=60, justify="right").pack(pady=2)

tk.Label(root, text=":תיקיית יעד שמירה", font=("Arial", 11)).pack(pady=5)
frame = tk.Frame(root)
frame.pack(pady=2)
tk.Entry(frame, textvariable=folder_var, width=48, justify="right").pack(side=tk.RIGHT, padx=5)
tk.Button(frame, text="בחר תיקייה...", command=browse_folder).pack(side=tk.LEFT)

tk.Label(root, text=":בחר פורמט הורדה", font=("Arial", 11)).pack(pady=5)
format_dropdown = ttk.Combobox(root, textvariable=format_var, values=["MP3", "MP4"], state="readonly", width=10, justify="center")
format_dropdown.pack(pady=2)

download_button = tk.Button(root, text="הורד", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", width=20, command=start_download)
download_button.pack(pady=15)

status_label = tk.Label(root, text="", font=("Arial", 10))
status_label.pack()

root.mainloop()