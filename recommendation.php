<?php
// Course Recommendation page loader

if (session_status() === PHP_SESSION_NONE) {
	session_start();
}

include __DIR__ . '/html/recommendation.html';
?>


