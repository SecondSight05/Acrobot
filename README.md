# Acrobot - The Magic 90's Word Game Reviver
Acrobot is an open source recreation of the Registration Server and IRC bot used in the 1997-2001 Berkeley Systems version of [Acrophobia](https://en.wikipedia.org/wiki/Acrophobia_(game)).
Now you too can experience the fear of Acronyms... through my horrible code. :)
<br>If you do want to improve this, go right ahead. You'll definitely do better then I did.

## Progress
This should mostly just work at this point, but still expect some bugs and whatnot.
<br>I never fully figured out that scoreboard at the end of the faceoff round...

## How to setup the server
You'll need a few things installed for this.
- [Python, any modern version will do.](https://www.python.org/downloads/)
- An IRC server. [InspIRCd](https://www.inspircd.org/) works the best for this.
  - The game likes to crash if too much is sent during IRC login...
- A web server, anything will work for this.
- A copy of the game, of course. Any version you find should work with this server.
  - Besides the WON version. That's a different beast entirely...
  - If you're struggling to find a copy, look in the archives for a CD of You Don't Know Jack Offline.

After you have everything, download [this ZIP file](https://secondzone.co.uk/vault/bezerk/AcroWebFiles.zip) containing everything you need for your web server.
<br>Place those files in the web server's root folder ("htdocs", for example).
<br>Now you just need to hex edit the game's main EXE file and replace `game01.acrophobia.com` with your web server's location.
<br>Start up Acrobot with `__main__.py`, open the game, and enjoy!
