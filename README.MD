# laffer-casino-extractor

This Python3 command-line tool can extract game assets from Larry's Casino designed by Al Lowe and produced by Sierra On-Line circa 1998.

[Reversed by: @deckarep @doomlazer](https://gist.github.com/deckarep/d6e0f0884a22c8a4a4b9392155f9dad0)

#
![Banner](LarryCasinoSpritesReversedBanner.png?raw=true "Larry Casino Sprite Extractor")
#

![Gameplay](gameplay.png?raw=true "Gameplay Screenshot")
#

The game is not easily playable on modern systems without the use of a virtual machine and *requires* that it be ran in 16-bit "high-color" mode with a resolution of 640x480. While I don't believe the sprite file-format has been reverse engineered prior; this repository might be a first.

This version of Larry's Casino should not be be confused with the older SCI-based mini-game: Crazy Nick's Software Picks: Leisure Suit Larry Casino which was a small single-disk game released by Sierra for $9.95 via mail-order.

This game was not a traditional SCI-based game and instead was built entirely on Windows 98 making use of DirectX, and GDI for rendering to the screen. It also had an online component that connected to Sierra's W.O.N. multi-player system which stands for World Opponent Network which is now defunct. W.O.N. was quite innovative for its time and helped fascilitate the push for online gaming as we know it today. Other efforts by Sierra also might be memorable: T.S.N - The Sierra Network and The Realm.

### What's Extracting 100%
- [x] Audio files
- [x] Large character sprites
- [x] Small character sprites
- [x] Most miscellaneous sprites and UI elements

### Not yet done
- [ ] Small percentage of sprites/UI elements
- [ ] Backgrounds
- [ ] Game scripts

### Installing
  1. Clone this repo
  2. Create the Python3 virtualenv: `python3 -m venv venv`
  3. Activate it: `source venv/bin/activate`
  4. Optional step: upgrade pip3
  5. Install the dependencies: `pip3 install -r requirements.txt`

### Usage
  0. Make sure you have a copy of the Larry Casino `RESOURCE.VOL` file.
  1. Run: `python3 main.py`
