from src.bot.storage.database import Database

def main():
    db = Database()
    db.insert_daily_traffic("2026-02-11", 200)  
    print(db.get_total_between("2026-02-11", "2026-02-11"))
    db.close()

if __name__ == "__main__":
    main()
