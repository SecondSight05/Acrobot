from configparser import ConfigParser
from cryptography.fernet import Fernet
import socket, logging, sqlite3, random, threading, string, time

class IRCClient():
    def start():
        # Get details from config file & setup stuff
        ConfigFile = ConfigParser()
        ConfigFile.read('data/config.ini')
        IRCLocation = ConfigFile['bezerk']['IRCServerLocation']
        IRCPort = int(ConfigFile['bezerk']['IRCServerPort'])
        IRCSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        EncKey = ConfigFile['bezerk']['FernetKey'].encode()
        encryption = Fernet(EncKey)
        ConfigFile = ''
        RoomState = ConfigParser()
        RoomState.read('data/roomstate.ini')
        RoomState['playerloc'] = {}
        RoomState['playername'] = {}
        RoomState['playerfmf'] = {}
        RoomState['playerinroom'] = {}
        RoomStateSync = ConfigParser()
        RoomStateSync.read('data/roomstate_sync.ini')
        RoomStateSync['playeronline'] = {}
        RoomStateSync['comptime'] = {}
        RoomStateSync['companswer'] = {}
        RoomStateSync['compnum'] = {}
        RoomStateSync['votedfor'] = {}
        
        # Setup the Find My Friends RoomState key for each player
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT * FROM accounts')
        for player in dbcursor:
            RoomStateSync['playeronline'][player[0]] = '0'
        with open('data/roomstate_sync.ini', 'w') as rssync:
            RoomStateSync.write(rssync)
        
        # Setup the RoomState keys for each room
        dbcursor.execute('SELECT * FROM rooms')
        for room in dbcursor:
            RoomState[room[1]] = {}
            RoomState[room[1]]['roomplayercount'] = '0'
            RoomState[room[1]]['roomhighscore'] = '0'
            RoomState[room[1]]['roommode'] = ''
            RoomState[room[1]]['roomplayerinfo'] = ''
            RoomStateSync[room[1]] = {}
            RoomStateSync[room[1]]['roomgametype'] = '0'
            RoomStateSync[room[1]]['companswercount'] = '0'
            RoomStateSync[room[1]]['companswers'] = ''
            RoomStateSync[room[1]]['category'] = ''
            RoomStateSync[room[1]]['roomcurrentstate'] = 'start_game'
            RoomStateSync[room[1]]['voterlist'] = ''
            RoomStateSync[room[1]]['speedwinner'] = ''
        dbcursor.close()
        database.close()
        
        # Setup logging
        IRCLog = logging.getLogger('Acrobot')
        IRCLog.setLevel(logging.DEBUG)
        LogFormatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        ConsoleLogging = logging.StreamHandler()
        ConsoleLogging.setLevel(logging.DEBUG)
        ConsoleLogging.setFormatter(LogFormatter)
        IRCLog.addHandler(ConsoleLogging)
        
        # Connect to the IRC server
        IRCLog.info('Connecting to the IRC server at ' + IRCLocation + ':' + str(IRCPort) + '...')
        IRCSock.connect((IRCLocation, IRCPort))
        IRCSock.send('USER BRAcrobot BRAcrobot BRAcrobot :Behold... The Magical Acrobot!\n'.encode())
        IRCSock.send('NICK Acrobot\n'.encode())
        IRCSock.send('PRIVMSG nickserv :BRAuth\r\n'.encode())
        chjoin = 0
        while True:
            msg = IRCSock.recv(2048)
            # Uncomment the line below to see IRC messages when they come in.
            IRCLog.info('New message: ' + str(msg))
            # Let's play Ping-Pong!
            if msg.find('PING'.encode()) != -1:
                IRCSock.send("PONG :don't worry, i'm still here\r\n".encode())
                # If this is the first time seeing "PING", join the channels.
                # (This is here because my IRC server has PING in one of its first messages, despite it not being an actual PING.)
                if chjoin == 0:
                    IRCLog.info('Joining channels...')
                    chjoinmsg = ''
                    IRCSock.send('JOIN #Acro_List\n'.encode())
                    database = sqlite3.connect('data/bezerk.db')
                    dbcursor = database.cursor()
                    dbcursor.execute('SELECT ChannelName FROM rooms')
                    for room2join in dbcursor:
                        chjoinmsg = chjoinmsg + 'JOIN #{}\n'.format(room2join[0])
                    IRCSock.send('{}'.format(chjoinmsg).encode())
                    dbcursor.close()
                    database.close()
                    chjoin = 1
                    IRCLog.info('Connected successfully.')
            
            # When a player joins a room, send logon_now to them privately.
            elif msg.find('JOIN'.encode()) != -1:
                if msg.find('Acrobot'.encode()) == -1:
                    JoinMessage = msg.decode('UTF-8')
                    JoinMessage = JoinMessage.split(':')
                    JoinIRCName = JoinMessage[1].split('!')
                    JoinIRCName = JoinIRCName[0]
                    JoinChannel = JoinMessage[2][:-2]
                    RoomState['playerloc'][JoinIRCName] = JoinChannel
                    IRCSock.send('PRIVMSG {} :logon_now\r\n'.format(JoinIRCName).encode())
            
            # Logon Processing
            elif msg.find('logon'.encode()) != -1:
                LogonMessage = msg.decode('UTF-8')
                LogonMessage = LogonMessage.split('"')
                LogonIRCName = LogonMessage[0].split('!')
                LogonIRCName = LogonIRCName[0].split(':')
                LogonIRCName = LogonIRCName[1]
                LogonChannel = RoomState['playerloc'][LogonIRCName]
                LogonResult = Acrophobia.logon(LogonMessage[1], LogonMessage[3], encryption)
                # If the logon was successful, then send logon_accepted to them privately.
                if LogonResult == 1:
                    IRCSock.send('PRIVMSG {} :logon_accepted\r\n'.format(LogonIRCName).encode())
                    RoomState['playerloc'][LogonIRCName] = LogonChannel[1:]
                    RoomState['playername'][LogonIRCName] = LogonMessage[1]
                    RoomState['playerfmf'][LogonMessage[1]] = LogonIRCName
                    RoomState['playerinroom'][LogonIRCName] = '0'
                    RoomStateSync['playeronline'][LogonMessage[1]] = '1'
                    with open('data/roomstate_sync.ini', 'w') as rssync:
                        RoomStateSync.write(rssync)
                    # Check if the player is in the room list channel. If they aren't, send sponsor_ad to them privately.
                    if LogonChannel != '#Acro_List':
                        IRCLog.info('Username ' + LogonMessage[1] + ' logged on to the ' + LogonChannel + ' room')
                        # Choose a random ad to be played as the "sponsor" ad.
                        with open('data/adlist.txt', 'r') as ads:
                            adlist = []
                            for ad in ads:
                                ad = ad.strip()
                                adlist.append(ad)
                        adchoice = random.choice(adlist)
                        IRCSock.send('PRIVMSG {} :sponsor_ad "{}"\r\n'.format(LogonIRCName, adchoice).encode())
                    # Otherwise, send the room list to them privately.
                    else:
                        database = sqlite3.connect('data/bezerk.db')
                        dbcursor = database.cursor()
                        IRCSock.send('PRIVMSG {} :start_list bot\r\n'.format(LogonIRCName).encode())
                        dbcursor.execute('SELECT * FROM rooms')
                        RoomJoinMsg = ''
                        for room in dbcursor:
                            # TBD: properly add the high score counter
                            RoomPlayerCount = int(RoomState[room[1]]['roomplayercount'])
                            RoomHighScore = int(RoomState[room[1]]['roomhighscore'])
                            RoomMode = RoomState[room[1]]['roommode']
                            RoomJoinMsg = RoomJoinMsg + f'PRIVMSG {LogonIRCName} :list_item bot 0 "{room[0]}" 0 "{IRCLocation}" {IRCPort} 0 "{room[1]}" 0 "Acrobot" {room[2]} "{RoomMode}" {str(RoomPlayerCount)} {str(RoomHighScore)} 0 {room[3]}\r\n'
                        IRCSock.send('{}'.format(RoomJoinMsg).encode())
                        dbcursor.close()
                        database.close()
                        IRCSock.send('PRIVMSG {} :end_list bot\r\n'.format(LogonIRCName).encode())
            
            # Set the player up for starting the actual game.
            elif msg.find('start_play'.encode()) != -1:
                StartPlayIRCName = msg[1:25].decode('UTF-8')
                StartPlayIRCName = StartPlayIRCName.split('!')
                StartPlayIRCName = StartPlayIRCName[0]
                # Get the room's name and current state.
                StartPlayChannel = RoomState['playerloc'][StartPlayIRCName]
                StartPlayRoomState = RoomStateSync[StartPlayChannel]['roomcurrentstate']
                IRCSock.send('PRIVMSG {} :current_state {}\r\n'.format(StartPlayIRCName, StartPlayRoomState).encode())
                # Get the room name/data from the DB and the player's username from RoomState.
                database = sqlite3.connect('data/bezerk.db')
                dbcursor = database.cursor()
                dbcursor.execute('SELECT RoomName FROM rooms WHERE ChannelName = ?', (StartPlayChannel,))
                dbresults = dbcursor.fetchone()
                StartPlayRoomName = dbresults[0]
                dbcursor.execute('SELECT * FROM rooms WHERE RoomName = ?', (StartPlayRoomName,))
                dbresults = dbcursor.fetchone()
                dbcursor.close()
                database.close()
                StartPlayUsername = RoomState['playername'][StartPlayIRCName]
                # Send the welcome message to the player privately.
                IRCSock.send('PRIVMSG {} :chat "Welcome to {}"\r\n'.format(StartPlayIRCName, StartPlayRoomName).encode())
                # Send the player join message to the room publicly.
                IRCSock.send('PRIVMSG #{} :player add "{}" 0 "{}"\r\n'.format(StartPlayChannel, StartPlayIRCName, StartPlayUsername).encode())
                # Check if there isn't anyone else in the room.
                RoomPlayerCount = int(RoomState[StartPlayChannel]['roomplayercount'])
                if RoomPlayerCount > 0:
                    # If false, send the info for the other players to the new player privately.
                    listplayeradd = 1
                    listplayerinfo = RoomState[StartPlayChannel]['roomplayerinfo'].split('/')
                    while listplayeradd <= RoomPlayerCount:
                        listplayeritem = listplayerinfo[listplayeradd].split(',')
                        ListPlayerIRCName = listplayeritem[0]
                        ListPlayerScore = listplayeritem[1]
                        ListPlayerUsername = listplayeritem[2]
                        IRCSock.send('PRIVMSG {} :player add "{}" {} "{}"\r\n'.format(StartPlayIRCName, ListPlayerIRCName, ListPlayerScore, ListPlayerUsername).encode())
                        listplayeradd += 1
                # Update the room info to show a new player.
                RoomState[StartPlayChannel]['roomplayercount'] = str(int(RoomState[StartPlayChannel]['roomplayercount']) + 1)
                RoomHighScore = int(RoomState[StartPlayChannel]['roomhighscore'])
                RoomMode = RoomState[StartPlayChannel]['roommode']
                RoomState[StartPlayChannel]['roomplayerinfo'] = RoomState[StartPlayChannel]['roomplayerinfo'] + '/' +  StartPlayIRCName + ',0,' + StartPlayUsername
                RoomState['playerinroom'][StartPlayIRCName] = '1'
                # Set the game type (Play or Practice) if that game type isn't already running, and a certain amount of players are in the room.
                if RoomStateSync[StartPlayChannel]['roomgametype'] == '0':
                    # Practice Mode
                    if RoomState[StartPlayChannel]['roomplayercount'] == '1' or RoomState[StartPlayChannel]['roomplayercount'] == '2':
                        RoomState[StartPlayChannel]['roommode'] = 'Practice'
                        RoomStateSync[StartPlayChannel]['roomgametype'] = '2'
                        with open('data/roomstate_sync.ini', 'w') as rssync:
                            RoomStateSync.write(rssync)
                        IRCSock.send('PRIVMSG {} :chat "There must be at least 3 players to start a game - You will be in Practice mode until then."\r\n'.format(StartPlayIRCName).encode())
                        threading.Thread(target=GameLoop.practice, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
                elif RoomStateSync[StartPlayChannel]['roomgametype'] == '2':
                    # Play Mode
                    if int(RoomState[StartPlayChannel]['roomplayercount']) >= 3:
                        RoomState[StartPlayChannel]['roommode'] = 'Play'
                        RoomStateSync[StartPlayChannel]['roomgametype'] = '1'
                        with open('data/roomstate_sync.ini', 'w') as rssync:
                            RoomStateSync.write(rssync)
                        IRCSock.send('PRIVMSG #{} :chat "A third player has joined - Get ready to play!"\r\n'.format(StartPlayChannel).encode())
                        threading.Thread(target=GameLoop.play, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
            
            # Logoff - Remove player from room.
            elif msg.find('logoff ip'.encode()) != -1 or msg.find('QUIT'.encode()) != -1:
                LogoffIRCName = msg[1:25].decode('UTF-8')
                LogoffIRCName = LogoffIRCName.split('!')
                LogoffIRCName = LogoffIRCName[0]
                if RoomState['playerloc'][LogoffIRCName].find('Acro_List') == -1 and RoomState['playerinroom'][LogoffIRCName] == '1':
                    # Get the channel that the player is in.
                    LogoffChannel = RoomState['playerloc'][LogoffIRCName]
                    # Find the other two pieces of info from RoomState.
                    logoffinfo = RoomState[LogoffChannel]['roomplayerinfo'].split('/')
                    for loitem in logoffinfo:
                        if loitem != '':
                            if loitem.find(LogoffIRCName) != -1:
                                loitem = loitem.split(',')
                                LogoffScore = loitem[1]
                                LogoffUsername = loitem[2]
                                IRCLog.info('Username ' + LogoffUsername + ' logged off of the #' + LogoffChannel + ' room')
                    # Get the index for the player's info in RoomState.
                    LogoffIndex = logoffinfo.index(LogoffIRCName + ',' + LogoffScore + ',' + LogoffUsername)
                    # Remove the player from the room in RoomState.
                    logoffinfo.pop(LogoffIndex)
                    logoffinfo = '/'.join(logoffinfo)
                    RoomState[LogoffChannel]['roomplayercount'] = str(int(RoomState[LogoffChannel]['roomplayercount']) - 1)
                    RoomState['playerinroom'][LogoffIRCName] = '0'
                    RoomStateSync['playeronline'][LogoffUsername] = '0'
                    # Update the in-game player list.
                    IRCSock.send('PRIVMSG #{} :player remove "{}" {} "{}"\r\n'.format(LogoffChannel, LogoffIRCName, LogoffScore, LogoffUsername).encode())
                    # Check if the room's game type needs to be changed.
                    if RoomStateSync[LogoffChannel]['roomgametype'] == '2':
                        if int(RoomState[LogoffChannel]['roomplayercount']) == 0:
                            # If there are no players left, close the loop for that room.
                            RoomStateSync[LogoffChannel]['roomgametype'] = '0'
                            RoomState[LogoffChannel]['roommode'] = ''
                            with open('data/roomstate_sync.ini', 'w') as rssync:
                                RoomStateSync.write(rssync)
            
            # Find My Friends
            elif msg.find('command find_player'.encode()) != -1:
                FMFIRCName = msg[1:25].decode('UTF-8')
                FMFIRCName = FMFIRCName.split('!')
                FMFIRCName = FMFIRCName[0]
                FMFUsername = msg.decode('UTF-8').split('"')
                FMFUsername = FMFUsername[1]
                # Check if the requested player is in the DB.
                database = sqlite3.connect('data/bezerk.db')
                dbcursor = database.cursor()
                dbcursor.execute('SELECT Username FROM accounts WHERE Username = ?', (FMFUsername,))
                dbresults = dbcursor.fetchone()
                if dbresults is None:
                    # If they aren't, send player_not_found.
                    dbcursor.close()
                    database.close()
                    IRCSock.send('PRIVMSG {} :player_not_found "{}"\r\n'.format(FMFIRCName, FMFUsername).encode())
                else:
                    # Otherwise, check if the requested player is online.
                    if RoomStateSync['playeronline'][FMFUsername] == '0' or dbresults is None:
                        dbcursor.close()
                        database.close()
                        # If they aren't, send player_not_found.
                        IRCSock.send('PRIVMSG {} :player_not_found "{}"\r\n'.format(FMFIRCName, FMFUsername).encode())
                    else:
                        # Otherwise, check if the requested player is in #Acro_List.
                        FMFIRCReq = RoomState['playerfmf'][FMFUsername]
                        if RoomState['playerloc'][FMFIRCReq].find('Acro_List') != -1:
                            dbcursor.close()
                            database.close()
                            # If they are, set the information to show they're choosing a room.
                            # Don't bother with getting the other details properly. They won't be shown anyway.
                            fmfroomname = 'a'
                            FMFChannel = 'b'
                            fmfisclean = '1'
                            RoomMode = 'c'
                            RoomPlayerCount = '0'
                            RoomHighScore = '0'
                            FMFRoomList = '1'
                        else:
                            # Otherwise, get all the information needed to show what room the requested player is in.
                            FMFChannel = RoomState['playerloc'][FMFIRCReq]
                            dbcursor.execute('SELECT RoomName, IsClean FROM rooms WHERE ChannelName = ?', (FMFChannel,))
                            dbresults = dbcursor.fetchone()
                            fmfroomname = dbresults[0]
                            fmfisclean = str(dbresults[1])
                            dbcursor.close()
                            database.close()
                            RoomPlayerCount = RoomState[FMFChannel]['roomplayercount']
                            RoomHighScore = RoomState[FMFChannel]['roomhighscore']
                            RoomMode = RoomState[FMFChannel]['roommode']
                            FMFRoomList = '0'
                        IRCSock.send(f'PRIVMSG {FMFIRCName} :player_found "{FMFUsername}" "{fmfroomname}" 0 "{IRCLocation}" {IRCPort} 0 "{FMFChannel}" 0 "Acrobot" {fmfisclean} "{RoomMode}" {RoomPlayerCount} {RoomHighScore} {FMFRoomList}\r\n'.encode())
            
            # When an acro is sent during the composition round.
            elif msg.find('response answer'.encode()) != -1:
                RAAcro = msg.decode('UTF-8')
                RAAcro = RAAcro.split('"')
                RATime = RAAcro[0].split(' ')
                RAAcro = RAAcro[1]
                RAPlayer = RATime[6]
                RATime = RATime[5]
                rsch = RoomState['playerloc'][RAPlayer]
                RoomStateSync[rsch]['companswers'] = RoomStateSync[rsch]['companswers'] + ',' + RAPlayer
                RoomStateSync[rsch]['companswercount'] = str(int(RoomStateSync[rsch]['companswercount']) + 1)
                RoomStateSync['comptime'][RAPlayer] = str(RATime)
                RoomStateSync['companswer'][RAPlayer] = RAAcro
                RoomStateSync['compnum'][RAPlayer] = RoomStateSync[rsch]['companswercount']
                RoomStateSync['votedfor'][RAPlayer] = ''
                # If this is the first acro submitted, then set the player to win the speed bonus.
                # Uh... maybe change this later? Comptime was already a thing...
                if RoomStateSync[rsch]['speedwinner'] == '':
                    RoomStateSync[rsch]['speedwinner'] = RAPlayer
                with open('data/roomstate_sync.ini', 'w') as rssync:
                    RoomStateSync.write(rssync)
                IRCSock.send('PRIVMSG #{} :answer_received {}\r\n'.format(rsch, RoomStateSync[rsch]['companswercount']).encode())
            
            # When a vote is sent during the voting round.
            elif msg.find('response vote'.encode()) != -1:
                # examples below
                # :ip3232249858!UnknownUse@90.192.224.189 PRIVMSG Acrobot :response vote ip1234567890 1
                # :ip3232249858!UnknownUse@90.192.224.189 PRIVMSG Acrobot :response vote ip1234567891 1
                # :ip3232249858!UnknownUse@90.192.224.189 PRIVMSG Acrobot :response vote ip1234567890 1
                # NOTE: if there's two ' next to each other, that's a ". change it to that.
                # NOTE 2: VOTES CAN BE CHANGED!!!
                RVVoted = msg.decode('UTF-8')
                RVVoted = RVVoted.split(' ')
                RVPlayer = RVVoted[0].split('!')
                RVPlayer = RVPlayer[0].split(':')
                RVPlayer = RVPlayer[1]
                RVVoted = RVVoted[5]
                print('RVPLAYER: ' + RVPlayer)
                print('RVVOTED: ' + RVVoted)
                RoomStateSync['votedfor'][RVPlayer] = RVVoted
                # If the player hasn't voted yet on this round, add them to the voterlist.
                vtrlistchk = RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'].split(',')
                if RVPlayer not in vtrlistchk:
                    RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'] = RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'] + ',' + RVPlayer
                with open('data/roomstate_sync.ini', 'w') as rssync:
                    RoomStateSync.write(rssync)
            
            # When a category is selected by the winning player.
            elif msg.find('response category'.encode()) != -1:
                RCCategory = msg.decode('UTF-8')
                RCCategory = RCCategory.split(' ')
                RCPlayer = RCCategory[0].split('!')
                RCCategory = RCCategory[5]
                RCPlayer = RCPlayer[0].split(':')
                RCPlayer = RCPlayer[1]
                RoomStateSync[RoomState['playerloc'][RCPlayer]]['category'] = RCCategory
                with open('data/roomstate_sync.ini', 'w') as rssync:
                    RoomStateSync.write(rssync)
            
            # Problem Player Complaints
            # TBD: QUOTES ARENT REMOVED (thankfully this doesn't effect acros)
            # TBD: figure out how to kick people out with enough complaints - it can't just be a certain amount, it could be abused
            elif msg.find('complain'.encode()) != -1:
                ComplainPlayer = msg.decode('UTF-8')
                ComplainReason = ComplainPlayer.split(':complain ')
                ComplainPlayer = ComplainPlayer.split('"')
                ComplainType = ComplainPlayer[0].split(' ')
                ComplainPlayer = ComplainPlayer[1]
                ComplainIRCName = ComplainType[0].split('!')
                ComplainType = int(ComplainType[5])
                ComplainReason = ComplainReason[1].split('{} "{}" '.format(str(ComplainType), ComplainPlayer))
                ComplainReason = ComplainReason[1].split('\r\n')
                ComplainReason = ComplainReason[0][:-1]
                ComplainIRCName = ComplainIRCName[0].split(':')
                ComplainIRCName = ComplainIRCName[1]
                ComplainTime = time.time()
                ComplainTimeDoc = time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime(ComplainTime))
                ComplainTime = time.strftime("%a-%d%b%Y-%H'%M'%S", time.gmtime(ComplainTime))
                if ComplainType == 1:
                    ComplainType = 'Bad Language'
                elif ComplainType == 2:
                    ComplainType = 'Harassment'
                else:
                    ComplainType = 'Other'
                ComplainReport = f'Player Game Name: {ComplainPlayer}\nPlayer IRC Name: {ComplainIRCName}\nReport Type: {ComplainType}\nReport Reason: {ComplainReason}\nReport Time: {ComplainTimeDoc}'
                ComplainFile = open('data/report-' + ComplainTime + '.txt', 'w')
                ComplainFile.write(ComplainReport)
                ComplainFile.close()
                IRCSock.send('PRIVMSG {} :chat "Thank you! Your complaint has been sent."\r\n'.format(ComplainIRCName).encode())

class GameLoop():
    def practice(IRCSock, RoomStateSync, GLChannel):
        AcroLetters = 3
        AcroCategory = 'General Acrophobia'
        PracticeLoop = True
        PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
        #time.sleep(4)
        #while PracticeLoop is True:
            # Composition Round (Practice)
            #if PracticeLoop == True:
                #IRCSock.send('PRIVMSG #{} :start_comp_round 2500 60000 1 "{}" "{}"\r\n'.format(GLChannel, Acrophobia.generateacro(AcroLetters), AcroCategory).encode())
            #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
            #time.sleep(78)
            # If there wasn't any composition round submissions, skip the category picker round.
            #if int(RoomStateSync[GLChannel]['companswercount']) > 0 and PracticeLoop == True:
                # In Practice Mode, the first person to submit an acro chooses the category.
                #CategoryChooser = RoomStateSync[GLChannel]['companswers'].split(',')
                #CategoryChooser = CategoryChooser[1]
                # Category Picker Round (Practice)
                #if PracticeLoop == True:
                    #IRCSock.send('PRIVMSG #{} :start_categories 2500 5000 1 "{}"\r\n'.format(GLChannel, CategoryChooser).encode())
                #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
                # Get the categories and show them to the player.
                #CategoryList = Acrophobia.getcategories()
                #if PracticeLoop == True:
                    #IRCSock.send('PRIVMSG #{} :start_list category\r\n'.format(GLChannel).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 0 "{}"\r\n'.format(GLChannel, CategoryList[0]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 1 "{}"\r\n'.format(GLChannel, CategoryList[1]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 2 "{}"\r\n'.format(GLChannel, CategoryList[2]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 3 "General Acrophobia"\r\n'.format(GLChannel).encode())
                    #IRCSock.send('PRIVMSG #{} :end_list category\r\n'.format(GLChannel).encode())
                #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
                #time.sleep(10)
                # If the bottom category or no category is chosen, set the next category to General Acrophobia.
                #if RoomStateSync[GLChannel]['category'] == '' or RoomStateSync[GLChannel]['category'] == '3':
                    #AcroCategory = 'General Acrophobia'
                # Otherwise, set the category to the one that was chosen.
                #else:
                    #AcroCategory = CategoryList[int(RoomStateSync[GLChannel]['category'])]
            # Increase the amount of letters in the next acronym by one. If it's over 7, set it back to 3.
            #AcroLetters += 1
            #if AcroLetters > 7:
                #AcroLetters = 3
            # Empty out the composition round answers.
            #if PracticeLoop == True:
                #RoomStateSync[GLChannel]['companswers'] = ''
                #RoomStateSync[GLChannel]['companswercount'] = '0'
                #RoomStateSync[GLChannel]['category'] = ''
            #with open('data/roomstate_sync.ini', 'w') as rssync:
                #RoomStateSync.write(rssync)
            #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
    
    def play(IRCSock, RoomStateSync, GLChannel):
        AcroLetters = 3
        AcroCategory = 'General Acrophobia'
        AcroRound = 1
        PlayLoop = True
        PlayLoop = GameLoop.loopcheck(GLChannel, 1, RoomStateSync)
        IRCSock.send('PRIVMSG #{} :start_game 8250\r\n'.format(GLChannel).encode())
        time.sleep(15)
        while PlayLoop is True:
            # Composition Round
            IRCSock.send('PRIVMSG #{} :start_comp_round 2500 60000 {} "{}" "{}"\r\n'.format(GLChannel, str(AcroRound), Acrophobia.generateacro(AcroLetters), AcroCategory).encode())
            PlayLoop = GameLoop.loopcheck(GLChannel, 1, RoomStateSync)
            time.sleep(78)
            if int(RoomStateSync[GLChannel]['companswercount']) > 0 and PlayLoop == True:
                AcroVotingTime = Acrophobia.givevotingtime(RoomStateSync[GLChannel]['companswercount'])
                AcroAnswers = RoomStateSync[GLChannel]['companswers'].split(',')
                IRCSock.send('PRIVMSG #{} :start_voting_round 2500 {}000 {}\r\n'.format(GLChannel, str(AcroVotingTime), AcroRound).encode())
                IRCSock.send('PRIVMSG #{} :start_list answer {} 1\r\n'.format(GLChannel, RoomStateSync[GLChannel]['companswercount']).encode())
                complistcount = 1
                while complistcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
                    IRCSock.send('PRIVMSG #{} :list_item answer {} "{}" "{}"\r\n'.format(GLChannel, str(complistcount - 1), AcroAnswers[complistcount], RoomStateSync['companswer'][AcroAnswers[complistcount]]).encode())
                    complistcount += 1
                IRCSock.send('PRIVMSG #{} :end_list answer\r\n'.format(GLChannel).encode())
                time.sleep(AcroVotingTime + 15)
                print('Doing Winner Calculation Now')
                AcroRoundWinner, AcroRoundVotes = Acrophobia.calcvotewinner(RoomStateSync, GLChannel, AcroAnswers)
                print('Vote Reveal Starting Now')
                IRCSock.send('PRIVMSG #{} :start_list vote_count\r\n'.format(GLChannel).encode())
                roundendcount = 1
                while roundendcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
                    #ADD AFTER SESSION:
                    #1. check if the player voted or not
                    #2. voters bonus points
                    # If the player didn't vote, then they lose all points gained during this round.
                    notlosingvotes = 1
                    if RoomStateSync['votedfor'][AcroAnswers[roundendcount]] == '':
                        notlosingvotes = 0
                    # If the player voted for the winner, then they get a Voters Bonus Point.
                    votersbp = 0
                    if RoomStateSync['votedfor'][AcroAnswers[roundendcount]] == AcroRoundWinner:
                        votersbp = 1
                    IRCSock.send('PRIVMSG #{} :list_item vote_count {} "{}" {} {} {}\r\n'.format(GLChannel, str(roundendcount - 1), AcroAnswers[roundendcount], AcroRoundVotes[roundendcount], notlosingvotes, votersbp).encode())
                    roundendcount += 1
                IRCSock.send('PRIVMSG #{} :end_list vote_count\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list voted_for\r\n'.format(GLChannel).encode())
                roundendcount = 1
                while roundendcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
                    #ADD AFTER SESSION:
                    #prevent traceback if a player doesn't vote
                    #MIGHT BE FIXED. the autoplay bots don't like me right now.
                    IRCSock.send('PRIVMSG #{} :list_item voted_for 1 "{}" "{}"\r\n'.format(GLChannel, AcroAnswers[roundendcount], RoomStateSync['votedfor'][AcroAnswers[roundendcount]]).encode())
                    roundendcount += 1
                IRCSock.send('PRIVMSG #{} :end_list voted_for\r\n'.format(GLChannel).encode())
                #ADD SCORE KEEPING AFTER SESSION
                #IRCSock.send('PRIVMSG #{} :start_list score\r\n'.format(GLChannel).encode())
                #roundendcount = 1
                if RoomStateSync[GLChannel]['speedwinner'] != '':
                    AcroSpeedWinner = RoomStateSync[GLChannel]['speedwinner']
                IRCSock.send('PRIVMSG #{} :start_scores 1 "{}" {} "{}" 2\r\n'.format(GLChannel, AcroRoundWinner, str(AcroLetters), AcroSpeedWinner).encode())
                time.sleep(45)
                IRCSock.send('PRIVMSG #{} :start_categories 2500 5000 1 "{}"\r\n'.format(GLChannel, AcroRoundWinner).encode())
                CategoryList = Acrophobia.getcategories()
                IRCSock.send('PRIVMSG #{} :start_list category\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 0 "{}"\r\n'.format(GLChannel, CategoryList[0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 1 "{}"\r\n'.format(GLChannel, CategoryList[1]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 2 "{}"\r\n'.format(GLChannel, CategoryList[2]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 3 "General Acrophobia"\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :end_list category\r\n'.format(GLChannel).encode())
                time.sleep(10)
                # If the bottom category or no category is chosen, set the next category to General Acrophobia.
                if RoomStateSync[GLChannel]['category'] == '' or RoomStateSync[GLChannel]['category'] == '3':
                    AcroCategory = 'General Acrophobia'
                # Otherwise, set the category to the one that was chosen.
                else:
                    AcroCategory = CategoryList[int(RoomStateSync[GLChannel]['category'])]
            AcroLetters += 1
            if AcroLetters > 7:
                AcroLetters = 3
            AcroRound += 1
            RoomStateSync[GLChannel]['companswers'] = ''
            RoomStateSync[GLChannel]['companswercount'] = '0'
            RoomStateSync[GLChannel]['category'] = ''
            RoomStateSync[GLChannel]['speedwinner'] = ''
            with open('data/roomstate_sync.ini', 'w') as rssync:
                RoomStateSync.write(rssync)
            # Every 3 rounds (or before the face-off), have an interstitial break.
            RunAdBreak = 0
            if AcroRound % 3 == 0:
                RunAdBreak = 1
            #ADD CHECK IF RIGHT BEFORE FACEOFF HERE LATER
            if RunAdBreak == 1:
                InterstitialList = Acrophobia.getinterstitials()
                IRCSock.send('PRIVMSG #{} :start_list download_ad\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item download_ad 1 {}\r\n'.format(GLChannel, InterstitialList[0]).encode())
                time.sleep(0.2)
                IRCSock.send('PRIVMSG #{} :list_item download_ad 2 {}\r\n'.format(GLChannel, InterstitialList[1]).encode())
                time.sleep(0.2)
                IRCSock.send('PRIVMSG #{} :list_item download_ad 3 {}\r\n'.format(GLChannel, InterstitialList[2]).encode())
                time.sleep(0.2)
                IRCSock.send('PRIVMSG #{} :end_list download_ad\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_ad 2500 20000 1\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list play_ad\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item play_ad 1 {}\r\n'.format(GLChannel, InterstitialList[0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item play_ad 2 {}\r\n'.format(GLChannel, InterstitialList[1]).encode())
                IRCSock.send('PRIVMSG #{} :list_item play_ad 3 {}\r\n'.format(GLChannel, InterstitialList[2]).encode())
                IRCSock.send('PRIVMSG #{} :end_list play_ad\r\n'.format(GLChannel).encode())
                time.sleep(45)
    
    def loopcheck(channel, isplaymode, RoomStateSync):
        if isplaymode == 0:
            if RoomStateSync[channel]['roomgametype'] == '0' or RoomStateSync[channel]['roomgametype'] == '1':
                return False
            else:
                return True
        elif isplaymode == 1:
            if RoomStateSync[channel]['roomgametype'] == '0' or RoomStateSync[channel]['roomgametype'] == '2':
                return False
            else:
                return True

class Acrophobia():
    def logon(LogonUsername, LogonPassword, encryption):
        # Get the account details from the database.
        # We're doing the checks again. (In case of a sneaky player...)
        # If any of the checks fail, return 0.
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT Username, Password, BadName, BanStatus FROM accounts WHERE Username = ?', (LogonUsername,))
        dbresults = dbcursor.fetchone()
        if dbresults is None:
            dbcursor.close()
            database.close()
            return 0
        # If the account exists in the database, then continue.
        else:
            dbcursor.close()
            database.close()
            # Check if the request password and DB password match.
            LogonPWMatch = encryption.decrypt(dbresults[1].encode()).decode()
            if LogonPassword != LogonPWMatch:
                return 0
            # If they do, then continue.
            else:
                LogonPassword = ''
                LogonPWMatch = ''
                # Check if the account has a bad name waiting to be changed.
                if dbresults[2] == 1:
                    return 0
                # If it doesn't, then continue.
                else:
                    # Check if the account is banned.
                    if dbresults[3] == 1:
                        return 0
                    # If it isn't, then the account is good to finish logon. Return 1.
                    else:
                        return 1
    
    # Generate a random acronym.
    def generateacro(letters):
        lettercount = 0
        letterselect = ''
        while lettercount < letters:
            randletter = random.choice(string.ascii_uppercase)
            # If the selected letter is X or Z, there's a much lower chance of it actually being added.
            if randletter == 'X' or randletter == 'Z':
                if random.randint(0, 100) < 11:
                    addletter = 1
                else:
                    addletter = 0
            # For any other letter, just immediately add it.
            else:
                addletter = 1
            if addletter == 1:
                letterselect = letterselect + randletter
                lettercount += 1
        return letterselect
    
    # Get three random categories.
    def getcategories():
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT * FROM categories ORDER BY RANDOM() LIMIT 3')
        dbresults = dbcursor.fetchall()
        dbcursor.close()
        database.close()
        CategoryList = [dbresults[0][0], dbresults[1][0], dbresults[2][0]]
        return CategoryList
    
    # Give the time for the current voting round.
    def givevotingtime(playercount):
        playercount = int(playercount)
        VotingTime = 20
        # The time increases depending on the player count, up to a maximum of 45 seconds.
        if playercount > 4:
            VotingTime = 5 * playercount
        if playercount >= 9:
            VotingTime = 45
        return VotingTime
    
    def calcvotewinner(RoomStateSync, GLChannel, AcroAnswers):
        ivlcount = 1
        voterlist = ''
        # Create the initial voter list.
        print('CVW - creating initial list')
        while ivlcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
            voterlist = voterlist + ',0'
            ivlcount += 1
        print('CVW - splitting list')
        voterlist = voterlist.split(',')
        votecount = 1
        votewinner = ''
        print('CVW - starting calculations')
        while votecount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
            nextvoter = AcroAnswers[votecount]
            voteindex = AcroAnswers.index(RoomStateSync['votedfor'][nextvoter])
            if voterlist[voteindex] != '':
                highscore = int(voterlist[voteindex]) + 1
                voterlist[voteindex] = str(highscore)
                if votewinner == '':
                    votewinner = AcroAnswers[voteindex]
                    winnerindex = voteindex
                elif highscore > int(voterlist[winnerindex]):
                    votewinner = AcroAnswers[voteindex]
                    winnerindex = voteindex
            voteindex += 1
            votecount += 1
            print('CVW - loop')
        return votewinner, voterlist
    
    # Choose three random ads to be in the ad break.
    def getinterstitials():
        with open('data/adlist.txt', 'r') as ads:
            adlist = []
            for ad in ads:
                ad = ad.strip()
                adlist.append(ad)
        adchoice1 = random.choice(adlist)
        adget = 0
        while adget != 1:
            adchoice2 = random.choice(adlist)
            if adchoice2 != adchoice1:
                adget = 1
        adget = 0
        while adget != 1:
            adchoice3 = random.choice(adlist)
            if adchoice3 != adchoice1 and adchoice3 != adchoice2:
                adget = 1
        adreturn = [adchoice1, adchoice2, adchoice3]
        return adreturn