SIMROAD PORTABLE DESKTOP APP
============================

No installation, Python setup, map download, account, or web hosting is needed.
The Kathmandu road map and SUMO simulation engine are included in this folder.

Windows
  Double-click Simroad.exe.

macOS / Linux
  Open a terminal in this folder and run ./Simroad.
  If needed once, run: chmod +x Simroad

The app opens its interface in your default browser. It listens only on
127.0.0.1 (this computer); it is not published to the internet or local network.
Keep the Simroad terminal open while using the app and press Ctrl+C to stop it.
Simulation outputs are saved under your per-user Simroad data directory.

This unsigned community build may trigger Windows SmartScreen or macOS Gatekeeper.
Only download it from the iamgroot400/simroad GitHub Releases page. On macOS,
Control-click the app and choose Open if Gatekeeper blocks the first launch.

The included map contains OpenStreetMap data for Kathmandu's trunk, primary, and
secondary roads and their connector links. Copyright OpenStreetMap contributors;
data is available under the Open Database License (ODbL):
https://www.openstreetmap.org/copyright

SUMO is distributed under EPL-2.0 or GPL-2.0-or-later. Its license and notices
are included with the packaged Python distribution metadata.
