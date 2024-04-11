from configparser import ConfigParser
from cryptography.fernet import Fernet
import logging, threading, sqlite3, os.path

from IRCClient import IRCClient as IRCListen
from greenroom import greenroom as GRListen

print("Acrobot - The Magic 90's Word Game Reviver")
print('Created by SecondSight')
print('')

# Setup logging and log first startup message
StartupLog = logging.getLogger('Startup')
StartupLog.setLevel(logging.DEBUG)
LogFormatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
ConsoleLogging = logging.StreamHandler()
ConsoleLogging.setLevel(logging.DEBUG)
ConsoleLogging.setFormatter(LogFormatter)
StartupLog.addHandler(ConsoleLogging)
StartupLog.info('Starting Acrobot...')

# Check if config/database files exist
# If not, set them up
# TBD: checks for if the data folder exists & adlist/badnames exist
database = sqlite3.connect('data/bezerk.db')
dbcursor = database.cursor()
dbcursor.execute('CREATE TABLE IF NOT EXISTS accounts (Username TEXT, Password TEXT, Adult INTEGER, BadName INTEGER, BanStatus INTEGER)')
dbcursor.execute('CREATE TABLE IF NOT EXISTS rooms (RoomName TEXT, ChannelName TEXT, IsClean INTEGER, SpecialInterest INTEGER)')
# TBD: room creation: since you have to create rooms manually right now, just make two rooms here - one in each category
# update: disabled these cause they were causing problems - wait for proper room creation
#dbcursor.execute('INSERT INTO rooms VALUES ("Acro Central", "Acro_AcroCentral", 1, 0)')
#dbcursor.execute('INSERT INTO rooms VALUES ("After Dark", "Acro_AfterDark", 0, 0)')
database.commit()
if os.path.isfile('data/config.ini') == False:
    ConfigFile = ConfigParser()
    ConfigFile.read('data/config.ini')
    ConfigFile['bezerk'] = {}
    ConfigFile['bezerk']['IRCServerLocation'] = '127.0.0.1'
    ConfigFile['bezerk']['IRCServerPort'] = '6667'
    ConfigFile['bezerk']['WebServerLocation'] = '127.0.0.1'
    ConfigFile['bezerk']['WebServerPort'] = '80'
    ConfigFile['bezerk']['FernetKey'] = Fernet.generate_key().decode('UTF-8')
    with open('data/config.ini', 'w') as newconfig:
        ConfigFile.write(newconfig)

# Connect to specified IRC server
threading.Thread(target=IRCListen.start).start()
# Start the web server
threading.Thread(target=GRListen.start).start()