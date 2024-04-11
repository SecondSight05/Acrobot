from configparser import ConfigParser
from cryptography.fernet import Fernet
import socket, logging, sqlite3

class greenroom():
    def start():
        # Get details from config file & setup stuff
        ConfigFile = ConfigParser()
        ConfigFile.read('data/config.ini')
        GRLocation = ConfigFile['bezerk']['WebServerLocation']
        GRPort = int(ConfigFile['bezerk']['WebServerPort'])
        GRSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        EncKey = ConfigFile['bezerk']['FernetKey'].encode()
        encryption = Fernet(EncKey)
        
        # Setup logging
        GRLog = logging.getLogger('GreenRoom')
        GRLog.setLevel(logging.DEBUG)
        LogFormatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        ConsoleLogging = logging.StreamHandler()
        ConsoleLogging.setLevel(logging.DEBUG)
        ConsoleLogging.setFormatter(LogFormatter)
        GRLog.addHandler(ConsoleLogging)
        
        # Start the web server
        GRLog.info('Starting the web server at ' + GRLocation + ':' + str(GRPort) + '...')
        GRSock.bind((GRLocation, GRPort))
        GRLog.info('Started successfully.')
        GRSock.listen()
        while True:
            ServerConnection, ServerConnAddr = GRSock.accept()
            msg = ServerConnection.recv(2048)
            # Uncomment the line below to see web requests when they come in.
            #print('greenroom request: ' + str(msg))
            if msg[5:21] == b'/cgi/acrval0.cgi':
                # Login (Validation)
                # PLEASE BE CAREFUL WHEN CHANGING THE RESPONSE!!! It's the only way I've found that the client will be happy when logging in.
                # Extract the details from the request.
                ValidateMessage = msg.decode('UTF-8')
                ValidateMessage = ValidateMessage.split('\r\n\r\n')
                ValidateMessage = ValidateMessage[1].split('&')
                # Check if the client is an older one - they use different responses...
                # (Older clients use "Username" instead of "User")
                # ...Depending on the client type, get the username from the request details differently.
                if ValidateMessage[0][0:5] == 'Usern':
                    ValidateOldClient = 1
                    ValidateUsername = ValidateMessage[0][9:]
                else:
                    ValidateOldClient = 0
                    ValidateUsername = ValidateMessage[0][5:]
                # Get the details for the account from the database.
                database = sqlite3.connect('data/bezerk.db')
                dbcursor = database.cursor()
                dbcursor.execute('SELECT Username, Password, Adult, BadName, BanStatus FROM accounts WHERE Username = ?', (ValidateUsername,))
                dbresults = dbcursor.fetchone()
                # If the account isn't in the DB, then set the return code to 5 (Account not found).
                if dbresults is None:
                    ValidateCode = 5
                    valerr = "User+Name+not+found.+If+you've+never+registered+before,+click+the+New+Member+button."
                    dbcursor.close()
                    database.close()
                else:
                    dbcursor.close()
                    database.close()
                    # Check if the entered password and the DB password match.
                    ValidatePassword = ValidateMessage[1][9:]
                    ValidatePWMatch = encryption.decrypt(dbresults[1].encode()).decode()
                    # If they don't, then set the return code to 6. (Password wrong)
                    if ValidatePassword != ValidatePWMatch:
                        ValidateCode = 6
                        valerr = 'The+User+Name+or+Password+is+incorrect.+Please+try+again.'
                        ValidatePassword = ''
                        ValidatePWMatch = ''
                        GRLog.info('Username ' + ValidateUsername + ' failed validation - Details mismatch')
                    else:
                        ValidatePassword = ''
                        ValidatePWMatch = ''
                        # Check if the account is banned.
                        # If it is, then set the return code to 10. (Account banned)
                        if dbresults[4] == 1:
                            ValidateCode = 10
                            valerr = 'This+user+has+been+BANNED.+Please+fill+out+the+unban+request+form+if+you+believe+there+has+been+an+error.'
                            GRLog.info('Username ' + ValidateUsername + ' failed validation - Banned')
                        else:
                            # Check if the account has a bad name waiting to be changed.
                            # It it does, then set the return code to 8. (Bad name)
                            if dbresults[3] == 1:
                                ValidateCode = 8
                                valerr = 'This+User+Name+is+unacceptable.+You+must+login+with+a+newer+version+of+Acrophobia+to+change+it.'
                                GRLog.info('Username ' + ValidateUsername + ' failed validation - Bad name')
                            # If everything looks good, then that's a successful validation. Set the return code to 0.999.
                            else:
                                ValidateCode = 0.999
                                GRLog.info('Successful validation for username ' + ValidateUsername)
                # Create the message to be sent.
                if ValidateCode < 5:
                    if ValidateOldClient == 1:
                        ValidateMessage = 'UserName=' + ValidateUsername + '&UserID=746&SessionID=6712950&RetCode=0&Message=Success'
                    else:
                        ValidateMessage = 'PlayerId=746&SessionId=6712950&Adult=' + str(dbresults[2]) + '&Result=0.999'
                else:
                    if ValidateOldClient == 1:
                        ValidateMessage = 'RetCode=' + str(ValidateCode) + '&Message=' + valerr
                    else:
                        ValidateMessage = 'Result=' + str(ValidateCode)
                vallen = len(ValidateMessage) + 1
                # Send the message.
                ServerConnection.send(bytes('HTTP/1.0 200 OK\r\nServer: BR-GreenRoom/1.0\r\nAccept-Ranges: bytes\r\nContent-Length: ' + str(vallen) + '\r\n\r\n' + ValidateMessage + '\n', 'utf-8'))
            
            elif msg[5:21] == b'/cgi/bezreg0.cgi':
                # Registration
                # Extract the details from the request.
                RegisterMessage = msg.decode('UTF-8')
                RegisterMessage = RegisterMessage.split('\r\n\r\n')
                RegisterMessage = RegisterMessage[1].split('&')
                # Check if the client is an older one - they use different responses (see above).
                if RegisterMessage[1][0:5] == 'Usern':
                    RegisterOldClient = 1
                    RegisterUsername = RegisterMessage[1][9:]
                else:
                    RegisterOldClient = 0
                    RegisterUsername = RegisterMessage[1][5:]
                # Check if the username isn't very nice.
                # WARNING: If editing badnames.txt, add one blank line at the end! Otherwise, you'll run into problems...
                RegisterBadName = 0
                with open('data/badnames.txt', 'r') as badnames:
                    for name in badnames:
                        if RegisterUsername.find(name[:-1]) != -1:
                            RegisterBadName = 1
                if RegisterBadName == 1:
                    RegisterCode = 8
                else:
                    # Set the value for if the player is over 18. (Adult Language rooms)
                    if int(RegisterMessage[6][-1]) == 0:
                        RegisterAdult = 0
                    else:
                        RegisterAdult = 1
                    # Encrypt the password.
                    RegisterPassword = encryption.encrypt(RegisterMessage[2][9:].encode()).decode()
                    # Check if the username already exists in the database.
                    database = sqlite3.connect('data/bezerk.db')
                    dbcursor = database.cursor()
                    dbcursor.execute('SELECT Username FROM accounts WHERE Username = ?', (RegisterUsername,))
                    dbresults = dbcursor.fetchone()
                    # If the account is found in the DB, then set the return code to 4. (Account already exists)
                    if dbresults != None:
                        RegisterCode = 4
                        regerr = 'This+User+Name+already+belongs+to+someone+else.+Please+choose+a+different+User+Name.'
                        dbcursor.close()
                        database.close()
                        RegisterPassword = ''
                        GRLog.info('New username ' + RegisterUsername + ' failed to register - Username in use')
                    else:
                        RegisterCode = 0
                        # Add the account to the database.
                        dbcursor.execute('INSERT INTO accounts VALUES (?, ?, ?, ?, ?)', (RegisterUsername, RegisterPassword, RegisterAdult, 0, 0))
                        database.commit()
                        dbcursor.close()
                        database.close()
                        RegisterPassword = ''
                        GRLog.info('Successful registration for new username ' + RegisterUsername)
                # Create the message to be sent.
                if RegisterCode < 4:
                    if RegisterOldClient == 1:
                        RegisterMessage = 'RetCode=' + str(RegisterCode) + '&Message=Thank+you+for+registering+for+beZerk.+Have+fun!'
                    else:
                        RegisterMessage = 'Result=' + str(RegisterCode)
                else:
                    if RegisterOldClient == 1:
                        RegisterMessage = 'RetCode=' + str(RegisterCode) + '&Message=' + regerr
                    else:
                        RegisterMessage = 'Result=' + str(RegisterCode)
                reglen = len(RegisterMessage) + 1
                # Send the message.
                ServerConnection.send(bytes('HTTP/1.0 200 OK\r\nServer: BR-GreenRoom/1.0\r\nAccept-Ranges: bytes\r\nContent-Length: ' + str(reglen) + '\r\n\r\n' + RegisterMessage + '\n', 'utf-8'))
            
            elif msg[5:24] == b'/cgi/bezchange0.cgi':
                # Bad Name Change
                # Extract the details from the request.
                NameMessage = msg.decode('UTF-8')
                NameMessage = NameMessage.split('\r\n\r\n')
                NameMessage = NameMessage[1].split('&')
                # Set the original details and new name.
                NameSet = NameMessage[2][5:]
                NameOriginal = NameMessage[0][13:]
                NamePassword = NameMessage[1][17:]
                # Check if the new username isn't very nice.
                # WARNING: If editing badnames.txt, add one blank line at the end! Otherwise, you'll run into problems...
                NameBad = 0
                with open('data/badnames.txt', 'r') as badnames:
                    for name in badnames:
                        if NameSet.find(name[:-1]) != -1:
                            NameBad = 1
                if NameBad == 1:
                    NameCode = 8
                    NamePassword = ''
                else:
                    # Check if the new username is already used.
                    database = sqlite3.connect('data/bezerk.db')
                    dbcursor = database.cursor()
                    dbcursor.execute('SELECT Username FROM accounts WHERE Username = ?', (NameSet,))
                    dbresults = dbcursor.fetchone()
                    if dbresults != None:
                        NameCode = 4
                        dbcursor.close()
                        database.close()
                        NamePassword = ''
                    else:
                        # Check if the original username and password match with the DB.
                        dbcursor.execute('SELECT Username, Password FROM accounts WHERE Username = ?', (NameOriginal,))
                        dbresults = dbcursor.fetchone()
                        NameUNMatch = dbresults[0]
                        NamePWMatch = encryption.decrypt(dbresults[1].encode()).decode()
                        if dbresults is None:
                            NameCode = 6
                            dbcursor.close()
                            database.close()
                            NamePassword = ''
                            NamePWMatch = ''
                        else:
                            if NameOriginal != NameUNMatch or NamePassword != NamePWMatch:
                                NameCode = 6
                                dbcursor.close()
                                database.close()
                            else:
                                # Change the username in the DB to the new one.
                                # (Also set BadName for the account back to 0.)
                                dbcursor.execute('UPDATE accounts SET Username = ? WHERE Username = ?', (NameSet, NameOriginal))
                                database.commit()
                                dbcursor.execute('UPDATE accounts SET BadName = 0 WHERE Username = ?', (NameSet,))
                                database.commit()
                                NameCode = 0
                                dbcursor.close()
                                database.close()
                                NamePassword = ''
                                NamePWMatch = ''
                                GRLog.info('New username ' + NameSet + ' set for username ' + NameOriginal)
                # Create the message to be sent.
                NameMessage = 'Result=' + str(NameCode)
                namelen = len(NameMessage) + 1
                # Send the message.
                ServerConnection.send(bytes('HTTP/1.0 200 OK\r\nServer: BR-GreenRoom/1.0\r\nAccept-Ranges: bytes\r\nContent-Length: ' + str(namelen) + '\r\n\r\n' + NameMessage + '\n', 'utf-8'))
            
            elif msg[4:15] == b'/rooms/acro':
                # Web Game Room List
                # TBD: change this sample data for real data based on the room list
                ServerConnection.send(b'HTTP/1.1 200 OK\r\nServer: BR-GreenRoom/1.0\r\nContent-Length: 2398\r\n\r\n<html>\r\n\r\n<head>\r\n<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">\r\n<title>AcroRoomList</title>\r\n</head>\r\n\r\n<body bgcolor="#000033" text="#FFFFFF">\r\n\r\n<p>This is only sample data at the moment.</p>\r\n<p align="center">Keep It Clean</p>\r\n<div align="center">\r\n\t<table border="1" width="400">\r\n\t\t<tr>\r\n\t\t\t<td valign="bottom">Room Name</td>\r\n\t\t\t<td valign="bottom" width="76">\r\n\t\t\t<p align="right">Number of<br>\r\n\t\t\tPlayers</td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right">Current<br>\r\n\t\t\tHigh<br>\r\n\t\t\tScore</td>\r\n\t\t\t<td width="76" valign="bottom">\r\n\t\t\t<p align="center">Mode</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td><font color="#FFCC33">Acro Central</font></td>\r\n\t\t\t<td width="76">\r\n\t\t\t<p align="right"><font color="#FFCC33">3</font></td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right"><font color="#FFCC33">29</td>\r\n\t\t\t<td width="76"><font color="#FFCC33">Play</font></td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td><font color="#777777">Acrodome</font></td>\r\n\t\t\t<td width="76">\r\n\t\t\t<p align="right"><font color="#777777">Full</font></td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right"><font color="#777777">35</td>\r\n\t\t\t<td width="76"><font color="#777777">Play</font></td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td><font color="#FFCC33">Flying Toaster</font></td>\r\n\t\t\t<td width="76">\r\n\t\t\t<p align="right"><font color="#FFCC33">1</font></td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right"><font color="#FFCC33">8</td>\r\n\t\t\t<td width="76"><font color="#FFCC33">Practice</font></td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td><font color="#00BF2F">Orion Blue</font></td>\r\n\t\t\t<td width="76">\r\n\t\t\t<p align="right"><font color="#00BF2F">0</font></td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right"><font color="#00BF2F">0</td>\r\n\t\t\t<td width="76"><font color="#00BF2F">&nbsp;</font></td>\r\n\t\t</tr>\r\n\t</table>\r\n<p>Adult Language</p>\r\n\t<table border="1" width="400">\r\n\t\t<tr>\r\n\t\t\t<td valign="bottom">Room Name</td>\r\n\t\t\t<td valign="bottom" width="76">\r\n\t\t\t<p align="right">Number of<br>\r\n\t\t\tPlayers</td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right">Current<br>\r\n\t\t\tHigh<br>\r\n\t\t\tScore</td>\r\n\t\t\t<td width="76" valign="bottom">\r\n\t\t\t<p align="center">Mode</td>\r\n\t\t</tr>\r\n\t\t<tr>\r\n\t\t\t<td><font color="#FFCC33">Dungeon</font></td>\r\n\t\t\t<td width="76">\r\n\t\t\t<p align="right"><font color="#FFCC33">3</font></td>\r\n\t\t\t<td width="48">\r\n\t\t\t<p align="right"><font color="#FFCC33">32</td>\r\n\t\t\t<td width="76"><font color="#FFCC33">Play</font></td>\r\n\t\t</tr>\r\n\t</table>\r\n\t</div>\r\n\r\n</body>\r\n\r\n</html>')
            
            else:
                # When all else fails, say that the request maker is in the wrong place (In case of a curious player).
                ServerConnection.send(b'HTTP/1.1 200 OK\r\nServer: BR-GreenRoom/1.0\r\nContent-Length: 132\r\n\r\n<html>\n<p>Sorry, but if you want to play, then you\'ll need to look somewhere else.</p>\n<p>In other words: ACCESS DENIED.</p>\n</html>')
            ServerConnection.close()