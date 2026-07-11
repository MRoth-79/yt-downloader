import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import yt_dlp
import os

def browse_folder():
    selected_dir = filedialog.askdirectory()
    if selected_dir:
        folder_var.set(selected_dir)

def start_download():
    url = url_var.get().strip()
    output_dir = folder_var.get().strip()
    format_type = format_var.get() # מקבל "MP3" או "MP4"
    
    if not url:
        messagebox.showerror("שגיאה", "אנא הכנס קישור מיוטיוב")
        return
    if not output_dir or not os.path.exists(output_dir):
        messagebox.showerror("שגיאה", "אנא בחר תיקיית יעד תקינה")
        return

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
            # מוריד את הוידאו והאודיו הטובים ביותר וממזג ל-mp4
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    status_label.config(text=f"מוריד {format_type}, אנא המתן...", fg="blue")
    root.update_idletasks()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        status_label.config(text="ההורדה הסתיימה בהצלחה!", fg="green")
        messagebox.showinfo("הצלחה", f"הסרטון ירד כקובץ {format_type} בהצלחה!")
    except Exception as e:
        status_label.config(text="ההורדה נכשלה", fg="red")
        messagebox.showerror("שגיאה בהורדה", f"התרחשה שגיאה:\n{str(e)}")

# עיצוב חלון ה-GUI
root = tk.Tk()
root.title("YouTube Media Downloader")
root.geometry("550x300")
root.resizable(False, False)

url_var = tk.StringVar()
folder_var = tk.StringVar(value=os.path.expanduser("~/Downloads"))
format_var = tk.StringVar(value="MP3") # ברירת מחדל

# אלמנטים על המסך
tk.Label(root, text=":קישור לסרטון מיוטיוב", font=("Arial", 11)).pack(pady=5)
tk.Entry(root, textvariable=url_var, width=60, justify="right").pack(pady=2)

tk.Label(root, text=":תיקיית יעד שמירה", font=("Arial", 11)).pack(pady=5)
frame = tk.Frame(root)
frame.pack(pady=2)
tk.Entry(frame, textvariable=folder_var, width=48, justify="right").pack(side=tk.RIGHT, padx=5)
tk.Button(frame, text="בחר תיקייה...", command=browse_folder).pack(side=tk.LEFT)

# הוספת תפריט בחירת פורמט (Dropdown)
tk.Label(root, text=":בחר פורמט הורדה", font=("Arial", 11)).pack(pady=5)
format_dropdown = ttk.Combobox(root, textvariable=format_var, values=["MP3", "MP4"], state="readonly", width=10, justify="center")
format_dropdown.pack(pady=2)

tk.Button(root, text="הורד", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", width=20, command=start_download).pack(pady=15)

status_label = tk.Label(root, text="", font=("Arial", 10))
status_label.pack()

root.mainloop()