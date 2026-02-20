# Voice Control Module

Voice channel control commands for stopping playback and disconnecting the bot. Auto-loaded when `tagging` or `music` modules are enabled.

## Commands

### `/stop`

Stop audio playback. Uses the `can_stop_playback` check — bot-moderators can always stop; regular users can only stop if they're alone with the bot in the voice channel.

### `/leave`

Make the bot leave the voice channel. Uses the `can_leave_voice` check — **bot-moderator only**.
