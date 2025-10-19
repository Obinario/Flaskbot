// Interactive client script for Course Recommendation page
(function initReco(){
    const btn = document.getElementById('get-recommendations');
    const results = document.getElementById('recommendation-results');
    const form = document.getElementById('recommendation-form');
    if (!btn || !results || !form) return;

    function renderRecommendations(items){
        if (!Array.isArray(items) || !items.length){
            results.innerHTML = '<div class="alert alert-warning">No recommendations available.</div>';
            return;
        }
        const rows = items.map(function(it, idx){
            const course = it.code || '';
            return `<tr>
                <td>${course}</td>
                <td>${it.name || ''}</td>
                <td>
                    <div class="btn-group btn-group-sm reco-rating-icons" role="group" aria-label="Rate" data-course="${course}">
                        <button type="button" class="btn btn-outline-success reco-rate-btn" data-rating="like" title="Like"><i class="bi bi-hand-thumbs-up"></i></button>
                        <button type="button" class="btn btn-outline-secondary reco-rate-btn" data-rating="neutral" title="Neutral"><i class="bi bi-dash-circle"></i></button>
                        <button type="button" class="btn btn-outline-danger reco-rate-btn" data-rating="dislike" title="Dislike"><i class="bi bi-hand-thumbs-down"></i></button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        results.innerHTML = [
            '<div class="table-responsive">',
            '<table class="table table-striped">',
            '<thead><tr><th>Code</th><th>Course</th><th>Your Rating</th></tr></thead>',
            `<tbody>${rows}</tbody>`,
            '</table>',
            '</div>',
            '<div class="mt-2">\
                <button type="button" id="submit-reco-ratings" class="btn btn-primary">\
                    <i class="bi bi-save"></i> Submit Ratings\
                </button>\
            </div>'
        ].join('');

        // handle icon selection (event delegation)
        results.addEventListener('click', function(e){
            const btn = e.target.closest('.reco-rate-btn');
            if (!btn) return;
            const group = btn.closest('.reco-rating-icons');
            if (!group) return;
            // toggle active state within group
            group.querySelectorAll('.reco-rate-btn').forEach(function(b){ b.classList.remove('active'); });
            btn.classList.add('active');
        });

        const submitBtn = document.getElementById('submit-reco-ratings');
        if (submitBtn){
            submitBtn.addEventListener('click', function(){
                const ratings = {};
                const groups = results.querySelectorAll('.reco-rating-icons');
                groups.forEach(function(group){
                    const course = group.getAttribute('data-course') || '';
                    const active = group.querySelector('.reco-rate-btn.active');
                    const val = active ? active.getAttribute('data-rating') : '';
                    if (course && val){ ratings[course] = val; }
                });
                if (!Object.keys(ratings).length){
                    results.insertAdjacentHTML('afterbegin', '<div class="alert alert-info">Please select at least one rating before submitting.</div>');
                    return;
                }
                const base = (window.RECO_API_BASE || '').replace(/\/$/, '');
                const payload = getFormData();
                fetch(base + '/api/save_ratings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        stanine: payload.stanine,
                        gwa: payload.gwa,
                        strand: payload.strand,
                        hobbies: payload.hobbies,
                        ratings: ratings
                    })
                })
                .then(function(r){ return r.json(); })
                .then(function(resp){
                    if (resp && typeof resp.saved !== 'undefined'){
                        results.insertAdjacentHTML('afterbegin', `<div class="alert alert-success">Saved ${resp.saved} rating(s). Thank you!</div>`);
                    } else if (resp && resp.error){
                        results.insertAdjacentHTML('afterbegin', `<div class="alert alert-danger">${resp.error}</div>`);
                    } else {
                        results.insertAdjacentHTML('afterbegin', '<div class="alert alert-warning">Unexpected response while saving ratings.</div>');
                    }
                })
                .catch(function(err){
                    results.insertAdjacentHTML('afterbegin', `<div class="alert alert-danger">${err && err.message ? err.message : 'Request failed'}</div>`);
                });
            });
        }
    }

    function getFormData(){
        const data = new FormData(form);
        return {
            stanine: data.get('stanine'),
            gwa: data.get('gwa'),
            strand: data.get('strand'),
            hobbies: data.get('hobbies')
        };
    }

    btn.addEventListener('click', function(){
        const base = (window.RECO_API_BASE || '').replace(/\/$/, '');
        if (!base){
            results.innerHTML = '<div class="alert alert-danger">Recommendation API base not configured.</div>';
            return;
        }
        const payload = getFormData();
        results.innerHTML = '<div class="alert alert-info"><i class="bi bi-hourglass-split me-2"></i>Getting recommendations...</div>';
        fetch(base + '/api/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(function(r){ return r.json(); })
        .then(function(data){
            if (data && data.recommendations){
                renderRecommendations(data.recommendations);
            } else if (data && data.error) {
                results.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            } else {
                results.innerHTML = '<div class="alert alert-warning">Unexpected response.</div>';
            }
        })
        .catch(function(err){
            results.innerHTML = `<div class="alert alert-danger">${err && err.message ? err.message : 'Request failed'}</div>`;
        });
    });
})();


