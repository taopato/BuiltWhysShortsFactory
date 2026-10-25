/* Fast review and platform visibility enhancements. */
function publicationBadges(job) {
  const configured = new Set(String(job.platforms || '').split(',').filter(Boolean));
  const planned = new Set((job.planned_platforms || []).flatMap(value => String(value).split(',')));
  const published = Object.fromEntries((job.publications || []).map(item => [item.platform, item]));
  return ['youtube', 'instagram', 'facebook', 'tiktok'].filter(platform => configured.has(platform) || published[platform]).map(platform => {
    const result = published[platform];
    let stateName = 'bekliyor';
    let stateClass = '';
    if (result?.status === 'published') { stateName = 'yayında'; stateClass = 'published'; }
    else if (result?.status === 'failed') { stateName = 'hata'; stateClass = 'rejected'; }
    else if (planned.has(platform)) { stateName = 'planlandı'; stateClass = 'planned'; }
    else if (job.status === 'approved') { stateName = 'hazır'; stateClass = 'planned'; }
    return `<span class="platform-badge ${stateClass}">${esc(platform)} · ${stateName}</span>`;
  }).join('');
}

const coreRenderJobs = renderJobs;
renderJobs = function renderJobsWithPlatforms() {
  coreRenderJobs();
  document.querySelectorAll('.video-card').forEach(card => {
    const job = state.jobs.find(item => item.id === card.dataset.id);
    const body = card.querySelector('.video-card-body');
    if (!job || !body) return;
    const platforms = document.createElement('div');
    platforms.className = 'platform-badges';
    platforms.innerHTML = publicationBadges(job);
    body.appendChild(platforms);
  });
};

const coreRenderDetail = renderDetail;
renderDetail = function renderDetailForFastReview() {
  coreRenderDetail();
  const job = state.selected;
  const body = document.querySelector('.detail-body');
  const actions = body?.querySelector('.actions');
  if (!body || !actions) return;

  const revisionSelect = body.querySelector('#revisionType');
  if (revisionSelect && !revisionSelect.querySelector('option[value="hybrid"]')) {
    const option = document.createElement('option');
    option.value = 'hybrid';
    option.textContent = 'Hibrit: Pexels + mekanizma animasyonu';
    revisionSelect.prepend(option);
  }
  const rejectButton = actions.querySelector('[data-action="reject"]');
  if (rejectButton) rejectButton.textContent = 'Konuyu ve tüm sürümleri iptal et';

  const quick = document.createElement('section');
  quick.className = 'quick-review';
  quick.innerHTML = `<div class="review-summary"><b>Özgünlük ve para kazanma güvenliği: ${job.originality_score || 0}/100</b><b>Teknik kalite: ${job.technical_score || 0}/100</b></div><div class="platform-badges">${publicationBadges(job)}</div>`;
  if (['pending_review', 'held'].includes(job.status)) {
    const label = document.createElement('label');
    label.innerHTML = '<input id="humanReview" type="checkbox"><span>Videoyu baştan sona izledim; anlatımı, görüntüleri ve bilgi doğruluğunu onaylıyorum.</span>';
    quick.appendChild(label);
  }
  actions.before(quick);

  if (job.revision_note) {
    const request = document.createElement('section');
    request.className = 'revision-request-summary';
    request.innerHTML = `<b>Bu sürümde uygulanması gereken revizyon:</b><p>${esc(job.revision_note)}</p>`;
    quick.after(request);
  }

  if ((job.family || []).length > 1) {
    const history = document.createElement('section');
    history.className = 'revision-history';
    history.innerHTML = `<b>Sürüm geçmişi</b>${job.family.map(item => `<small>V${item.version} · ${esc(statusNames[item.status] || item.status)}${item.revision_note ? ` · ${esc(item.revision_note)}` : ''}</small>`).join('')}`;
    body.querySelector('.form-grid')?.before(history);
  }

  if (job.status === 'published' || (job.publications || []).some(item => item.status === 'published')) {
    const snapshots = Object.fromEntries((job.analytics || []).map(item => [item.platform, item]));
    const publicationMap = Object.fromEntries((job.publications || []).map(item => [item.platform, item]));
    const platforms = [...new Set([
      ...Object.keys(publicationMap), ...Object.keys(snapshots),
    ])];
    const analytics = document.createElement('section');
    analytics.className = 'published-analytics';
    analytics.innerHTML = `<div class="published-analytics-head"><div><b>Video performansı</b><small>Bu videonun platform bazlı son ölçümü</small></div><button type="button" class="ghost small" id="refreshVideoAnalytics">Yenile</button></div><div class="published-analytics-grid">${platforms.map(platform => {
      const metric = snapshots[platform];
      const publication = publicationMap[platform];
      const link = publication?.remote_url ? `<a href="${esc(publication.remote_url)}" target="_blank" rel="noopener">Yayını aç</a>` : '';
      return `<article class="video-analytic-card"><div><strong>${esc(platform)}</strong>${link}</div>${metric ? `<div class="video-analytic-numbers"><span><b>${fmt(metric.views)}</b><small>İzlenme</small></span><span><b>${fmt(metric.likes)}</b><small>Beğeni</small></span><span><b>${fmt(metric.comments)}</b><small>Yorum</small></span><span><b>${fmt(metric.shares)}</b><small>Paylaşım</small></span></div><p>Ort. izlenme: %${Number(metric.average_view_percentage || 0).toFixed(1)} · Kazanılan takipçi: ${fmt(metric.followers_gained)} · ${date(metric.captured_at)}</p>` : `<p>Yayın bağlantısı var; bu video için ilk analitik ölçümü henüz gelmedi.</p>`}</article>`;
    }).join('') || '<p>Henüz bağlı bir platform yayını bulunamadı.</p>'}</div>`;
    quick.after(analytics);
    analytics.querySelector('#refreshVideoAnalytics').onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Alınıyor...';
      try {
        await api('/api/analytics/refresh', { method: 'POST' });
        state.selected = await api(`/api/jobs/${job.id}`);
        renderDetail();
        addLanguageControl();
        toast('Video analitiği yenilendi');
      } catch (error) {
        toast(error.message, true);
      }
    };
  }

  const visibility = document.createElement('label');
  visibility.className = 'youtube-visibility';
  visibility.innerHTML = '<span>YouTube görünürlüğü</span><select id="youtubePrivacy"><option value="private">Gizli</option><option value="unlisted">Liste dışı</option><option value="public">Herkese açık</option></select>';
  visibility.querySelector('select').value = job.youtube_privacy || 'private';
  actions.after(visibility);
  if (job.status === 'approved') {
    const publishNow = document.createElement('button');
    publishNow.className = 'primary';
    publishNow.textContent = 'Şimdi yayın kuyruğuna al';
    publishNow.onclick = () => {
      if (confirm('Bu onaylı videoyu seçili platformlarda şimdi yayın kuyruğuna almak istiyor musun?')) jobAction('publish_now');
    };
    actions.appendChild(publishNow);
  }
};

saveJob = async function saveJobWithVisibility() {
  const platforms = selectedPlatforms();
  if (!platforms) return toast('En az bir platform seç.', true);
  try {
    state.selected = await api(`/api/jobs/${state.selected.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        title: document.querySelector('#editTitle').value,
        topic: document.querySelector('#editTopic').value,
        script: document.querySelector('#editScript').value,
        description: document.querySelector('#editDescription').value,
        hashtags: document.querySelector('#editHashtags').value,
        quality_score: Number(document.querySelector('#editQuality').value),
        language: document.querySelector('#editLanguage')?.value || state.selected.language,
        platforms,
        youtube_privacy: document.querySelector('#youtubePrivacy')?.value || 'private',
      }),
    });
    toast('Video bilgileri kaydedildi');
    renderDetail();
    addLanguageControl();
    loadJobs();
  } catch (error) { toast(error.message, true); }
};

jobAction = async function guardedJobAction(action, revision_type = 'visuals') {
  let note = '';
  if (['reject', 'revision', 'reject_family'].includes(action)) {
    note = prompt(action === 'revision' ? 'Revizyon notu:' : 'Red sebebi:', action === 'revision' ? '' : 'İçerik uygun değil') || '';
    if (action === 'reject_family' && !note) return;
  }
  const human_confirmed = action === 'approve' && Boolean(document.querySelector('#humanReview')?.checked);
  if (action === 'approve' && !human_confirmed) return toast('Önce videoyu izlediğini onaylayan kutuyu işaretle.', true);
  try {
    state.selected = await api(`/api/jobs/${state.selected.id}/action`, {
      method: 'POST', body: JSON.stringify({ action, note, revision_type, human_confirmed }),
    });
    toast('İşlem kaydedildi');
    renderDetail();
    addLanguageControl();
    loadJobs();
    loadDashboard();
  } catch (error) { toast(error.message, true); }
};
