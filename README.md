# e-badge-web
webinterface to control e-paper display

## Setup
### Install Dependencies
    
    # System dependencies
    apt install git python3-venv libopenjp2-7

    # e-badge-web
    git clone https://github.com/razurac/e-badge-web.git
    python -m venv --system-site-packages e-badge-web/.venv
    source e-badge-web/.venv/bin/activate
    pip3 install -r e-badge-web/requirements.txt

    # WaveShare e-paper python libs
    git clone https://github.com/waveshare/e-Paper.git
    pip install e-Paper/RaspberryPi_JetsonNano/python/

### Enable Interfaces

    # SPI
    sudo raspi-config
    -> Interface Options -> SPI -> yes -> ok -> finish

### (optional) Auto start on boot
This assumes you are using user "pi". If you are running as a different user, change all files and commands
accordingly.

    sudo loginctl enable-linger pi
    mkdir -p ~/.local/share/systemd/user/
    cp /home/pi/e-badge-web/autostart/epd-web.service ~/.local/share/systemd/user/
    systemctl --user enable --now epd-web.service

## Usage
Open Web-Ui at address dispplayed by the e-paper
