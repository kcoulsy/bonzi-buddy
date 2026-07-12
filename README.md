# Bonzi for Linux

A port of *BonziBUDDY Rewritten* — the purple Microsoft Agent desktop pet. There are few reasons for porting this:
 - the original was getting flagged as malware and I wanted to inspect the code
 - the original required .NET framework 2.0
 - I wanted it to be cross platform compatible as I use linux
 - I wanted the source code to be open so it can be reviewed that it's not a virus

## Run

```bash
./run.sh
```

## Voice (optional)

Install any one TTS engine for Bonzi to actually talk (otherwise the balloon
still shows):

```bash
sudo pacman -S espeak-ng        # recommended
# or: festival, or speech-dispatcher (spd-say)
```
