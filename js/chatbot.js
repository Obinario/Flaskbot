// Interactive client script for AI Chatbot page
(function initChatbot(){
	const chatContainer = document.getElementById('chatContainer');
	const typingIndicator = document.getElementById('typingIndicator');
	const userInput = document.getElementById('userInput');
	const sendButton = document.getElementById('sendButton');
	const faqOptionsBar = document.getElementById('faqOptionsBar');
	let loadedFaqs = [];

	if (!chatContainer || !userInput || !sendButton) return;

	function addMessage(text, sender){
		const messageDiv = document.createElement('div');
		messageDiv.className = `message ${sender}-message`;
		if (sender === 'bot'){
			let formattedText = String(text || '')
				.replace(/\n/g, '<br>')
				.replace(/^-\s+(.+)$/gm, '<li>$1<\/li>')
				.replace(/^(\d+)\.\s+(.+)$/gm, '<li>$2<\/li>')
				.replace(/(<li>.*<\/li>)/s, '<ul>$1<\/ul>');
			formattedText = formattedText.replace(/<br><br><br>/g, '<br><br>');
			messageDiv.innerHTML = formattedText || '';
		} else {
			messageDiv.innerHTML = String(text || '');
		}
		chatContainer.appendChild(messageDiv);
		chatContainer.scrollTop = chatContainer.scrollHeight;
	}

	function showTyping(){
		if (typingIndicator) typingIndicator.style.display = 'block';
		chatContainer.scrollTop = chatContainer.scrollHeight;
	}

	function hideTyping(){
		if (typingIndicator) typingIndicator.style.display = 'none';
	}

	function askQuestion(question){
		addMessage(question, 'user');
		showTyping();
		var base = (window.CHATBOT_API_BASE || '').replace(/\/$/, '');
		fetch(base + '/ask_question', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ question: question })
		})
		.then(function(response){ return response.json(); })
		.then(function(data){
			hideTyping();
			addMessage(data && data.answer ? data.answer : 'No response received.', 'bot');
			if (data && Array.isArray(data.suggested_questions) && data.suggested_questions.length){
				renderFaqOptions(data.suggested_questions);
			}
		})
		.catch(function(){
			hideTyping();
			addMessage('Sorry, there was a problem contacting the chatbot service.', 'bot');
		});
	}

	function renderFaqOptions(questions){
		if (!faqOptionsBar) return;
		faqOptionsBar.innerHTML = '';
		questions.forEach(function(q){
			const el = document.createElement('div');
			el.className = 'faq-option';
			el.textContent = q;
			el.addEventListener('click', function(){ askQuestion(q); });
			faqOptionsBar.appendChild(el);
		});
		faqOptionsBar.style.display = questions.length ? '' : 'none';
	}

	function scoreQuestion(query, question){
		var q = (query || '').toLowerCase();
		var s = (question || '').toLowerCase();
		if (!q) return 0;
		var score = 0;
		if (s.startsWith(q)) score += 3;
		if (s.includes(q)) score += 2;
		// token overlap
		var qt = q.split(/\s+/).filter(Boolean);
		var st = s.split(/\s+/).filter(Boolean);
		if (qt.length && st.length){
			var setS = new Set(st);
			var overlap = 0;
			for (var i=0;i<qt.length;i++){ if (setS.has(qt[i])) overlap++; }
			score += overlap * 1.5;
		}
		return score;
	}

	function getTopMatches(query, limit){
		if (!Array.isArray(loadedFaqs) || !loadedFaqs.length) return [];
		var items = loadedFaqs.map(function(f){ return f.question || ''; });
		if (!query) return items.slice(0, limit || 8);
		var ranked = items.map(function(q){
			return { q: q, s: scoreQuestion(query, q) };
		}).filter(function(r){ return r.s > 0; });
		ranked.sort(function(a, b){ return b.s - a.s; });
		return ranked.slice(0, limit || 8).map(function(r){ return r.q; });
	}

	function sendMessage(){
		const message = (userInput.value || '').trim();
		if (!message) return;
		askQuestion(message);
		userInput.value = '';
	}

	// Wire events
	sendButton.addEventListener('click', sendMessage);
	userInput.addEventListener('keypress', function(e){
		if (e.key === 'Enter') sendMessage();
	});

	// Optionally render preloaded FAQs if provided globally (e.g., window.FAQS)
	if (Array.isArray(window.FAQS) && window.FAQS.length){
		loadedFaqs = window.FAQS.map(function(f){ return typeof f === 'string' ? { question: f } : f; });
		renderFaqOptions(getTopMatches('', 8));
	} else {
		// Fetch FAQs from Flask if available
		var base = (window.CHATBOT_API_BASE || '').replace(/\/$/, '');
		if (base){
			fetch(base + '/faqs')
				.then(function(r){ return r.json(); })
				.then(function(payload){
					if (payload && Array.isArray(payload.faqs) && payload.faqs.length){
						loadedFaqs = payload.faqs;
						renderFaqOptions(getTopMatches('', 8));
					} else {
						// show a subtle note in the chat if no FAQs
						addMessage('No FAQs available at the moment.', 'bot');
					}
				})
				.catch(function(err){
					addMessage('Failed to load FAQs. Please try again later.', 'bot');
				});
		}
	}

	// Update FAQ suggestions as user types
	userInput.addEventListener('input', function(){
		var q = (userInput.value || '').trim();
		var top = getTopMatches(q, 8);
		renderFaqOptions(top);
	});
})();

