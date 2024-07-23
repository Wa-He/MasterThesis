const int channels[] = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13};
const int lower_channel_lim = 6;
const int upper_channel_lim = 9;

bool channel_status[] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
const int numChannels = sizeof(channel_status) / sizeof(channel_status[0]);

unsigned long current_time = 0;
unsigned long previous_flush_time = 0;
unsigned long previous_status_time = 0;


void setup() {
  Serial.begin(9600);
  initializeRelays();  // set all pins to OUTPUT and LOW
  Serial.flush();
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    switch (command) {
      case 'O':
      case 'o':
        openRelay();
        break;
      case 'C':
      case 'c':
        closeRelay();
        break;
      case 'A':
      case 'a':
        openAllRelays();
        break;
      case 'L':
      case 'l':
        closeAllRelays();
        break;
      case 'S':
      case 's':
        printStatus();
    }
  }
  current_time = millis();
  // flush buffer every 10 seconds
  if (current_time >= previous_flush_time + 10000){
    Serial.flush();
    previous_flush_time = current_time;
  }
  /* always print status
  if (current_time >= previous_status_time + 500) {
    printStatus();
    previous_status_time = current_time;
  }
  */
  
}


void initializeRelays() {
  for (int i = lower_channel_lim-2; i <= upper_channel_lim-2; i++) {
    pinMode(channels[i], OUTPUT);
    digitalWrite(channels[i], HIGH);  // Initial state: relays are off
    channel_status[i] = 0;
  }
}

void openRelay() {
  int relayNumber = Serial.parseInt();  // Read the relay number
  if (relayNumber >= lower_channel_lim && relayNumber <= upper_channel_lim) {
    digitalWrite(channels[relayNumber - 2], LOW);  // Turn on the specified relay
    // Serial.println("Relay " + String(relayNumber) + " is OPEN");
    channel_status[relayNumber - 2] = 1;
  } else {
    // Serial.println("Invalid relay number");
  }
}

void closeRelay() {
  int relayNumber = Serial.parseInt();  // Read the relay number
  if (relayNumber >= lower_channel_lim && relayNumber <= upper_channel_lim) {
    digitalWrite(channels[relayNumber - 2], HIGH);  // Turn off the specified relay
    // Serial.println("Relay " + String(relayNumber) + " is CLOSED");
    channel_status[relayNumber - 2] = 0;
  } else {
    // Serial.println("Invalid relay number");
  }
}

void openAllRelays() {
  for (int i = lower_channel_lim-2; i <= upper_channel_lim-2; i++) {
    digitalWrite(channels[i], LOW);  // Turn on all relays
    channel_status[i] = 1;
  }
  // Serial.println("All relays are OPEN");
}

void closeAllRelays() {
  for (int i = lower_channel_lim-2; i <= upper_channel_lim-2; i++) {
    digitalWrite(channels[i], HIGH);  // Turn off all relays
    channel_status[i] = 0;
  }
  // Serial.println("All relays are CLOSED");
}

void printStatus() {
  Serial.print("Status: ");
  for (int i = 0; i < numChannels; i++) {
    Serial.print(channel_status[i]);
    if (i < numChannels-1) {
      Serial.print(", "); // Print a comma and space between elements
    }
  } 
  Serial.println();
}