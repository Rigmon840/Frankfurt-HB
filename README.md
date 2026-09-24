# USB-Stick-Ersteller in Python

Starte `usb_stick_ersteller.py` mit Python 3. Die Oberflaeche bietet zwei Schritte:

1. Klicke auf **EXE auswaehlen...** und waehle die auszufuehrende Datei.
2. Waehle den USB-Stick und klicke auf **Stick erstellen**.
3. Klicke auf **Ueberwachung starten**. Beim spaeteren Einstecken eines vorbereiteten Sticks wird die kopierte EXE gestartet.
4. Auf einem neuen PC kannst du alternativ `START_USB.bat` auf dem Stick doppelt anklicken. Dafuer muss Python auf dem neuen PC nicht installiert sein.

Auf dem Stick werden die ausgewaehlte EXE, `START_USB.bat` und `usb_auto_start.json` gespeichert. Windows erlaubt aus Sicherheitsgruenden keinen automatischen Start direkt durch das Einstecken eines USB-Sticks. Deshalb muss dieses Python-Programm auf dem PC laufen, wenn das Oeffnen wirklich beim Einstecken passieren soll. Eine `autorun.inf`-Datei waere auf aktuellen Windows-PCs keine funktionierende Loesung.