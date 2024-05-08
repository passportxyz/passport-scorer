
#!/bin/bash

API_KEY="u480904-3f4b283b8db86d6a84a65cf3"  # this is for `engineering@gitcoin.co`
URL="https://api.uptimerobot.com/v2/newMonitor"
HEARTBEAT_TYPE=5
FRIENDLY_NAME="$1"  # First argument is the friendly name
INTERVAL_SECONDS="$2" # Must be a multiple of 60
ALERT_CONTACTS="3708329" # Passport Scorer PagerDuty
RANDOM="$3" # random arg to easily retrigger the script from pulumi
# NOTE: Not clear how to modify grace period 

# get_alerts() {
#     local body="{
#         \"api_key\":\"$API_KEY\"
#     }";
#     local curl_cmd=$(curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: application/json" -d "$body" "https://api.uptimerobot.com/v2/getAlertContacts");
#     echo $curl_cmd
# }

# get_monitor(){
#     local body="{
#         \"api_key\":\"$API_KEY\"
#     }";
#     local curl_cmd=$(curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: application/json" -d "$body" "https://api.uptimerobot.com/v2/getMonitors");
#     echo $curl_cmd
# }

create_heartbeat_monitor() {
    local body="{
        \"api_key\":\"$API_KEY\", 
        \"type\":\"$HEARTBEAT_TYPE\", 
        \"interval\":\"$INTERVAL_SECONDS\", 
        \"timeout\":\"60\", 
        \"friendly_name\": \"$FRIENDLY_NAME\",
        \"alert_contacts\": \"$ALERT_CONTACTS\"
    }";
    # echo $body
    local curl_cmd=$(curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: application/json" -d "$body" $URL)  

    echo $curl_cmd

    # local success=$(echo "$response" | jq -r '.stat')
    
    # if [[ $success == "ok" ]]; then
    #     local monitor_id=$(echo "$response" | jq -r '.monitor.id')
    #     echo "Heartbeat monitor created successfully! \n Monitor ID: $monitor_id"
    # else
    #     echo "\n Failed to create heartbeat monitor.\n"
    #     echo "$response"
    # fi
}

# get_alerts
create_heartbeat_monitor
