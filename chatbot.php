<?php
// Chatbot page loader
// No auth required; shows navbar, mobile nav, and sidebar like other pages

// Ensure sessions for navbar/mobile templates
if (session_status() === PHP_SESSION_NONE) {
	session_start();
}

// Include HTML template
include __DIR__ . '/html/chatbot.html';
?>


