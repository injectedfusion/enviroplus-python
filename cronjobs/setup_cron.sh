
#!/bin/bash

# Example cronjob to run sensorcommunity_combined executable every day at midnight
(crontab -l ; echo "0 0 * * * $PWD/dist/sensorcommunity_combined") | crontab -