/**
 * Meeting Details Page JavaScript
 * Displays comprehensive AI Closer analysis with enterprise CRM styling
 */

const MEETING_ID = new URLSearchParams(window.location.search).get('id');

async function loadMeetingAnalysis() {
  if (!MEETING_ID) {
    showToast('No meeting ID provided', 'error');
    return;
  }

  try {
    // Fetch the analysis (adjust endpoint as needed)
    const response = await fetch(`/api/meetings/${MEETING_ID}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error('Failed to load meeting analysis');
    }

    const data = await response.json();
    populateAnalysisUI(data);
  } catch (error) {
    console.error('Error loading meeting:', error);
    showToast('Failed to load meeting analysis', 'error');
  }
}

function populateAnalysisUI(data) {
  // Extract from final_report or fallback to individual reports
  const report = data.final_report || {};

  // Helper: sanitize enums and only allow known values to avoid exposing backend objects
  const allowedSentiments = ['Positive','Cautiously Optimistic','Neutral','Cautiously Pessimistic','Negative'];
  const allowedStages = ['Cold','Interested','Qualified','SQL','Negotiation','Near Closing'];
  const allowedStrengths = ['Weak','Moderate','Strong'];
  const allowedObjectionCategories = ['Budget/Pricing','Technical/Integration','Timing/Urgency','Trust/Vendor','Adoption/Change','Other'];

  function safeEnum(value, allowed, fallback) {
    if (!value || typeof value !== 'string') return fallback;
    // Strip any python-like class artifacts
    const simple = value.split('.').pop().trim();
    for (const a of allowed) {
      if (simple.toLowerCase() === a.toLowerCase()) return a;
    }
    return fallback;
  }

  function formatConfidenceBadge(score) {
    if (score == null) return '';
    const s = Number(score);
    if (isNaN(s)) return '';
    const cls = s >= 80 ? 'confidence-high' : s >= 60 ? 'confidence-medium' : 'confidence-low';
    return `<span class="confidence-badge ${cls}">${s}%</span>`;
  }

  function renderEvidence(evidence) {
    if (!evidence) return '';
    return `<div class="evidence">"${escapeHtml(evidence)}"</div>`;
  }

  // Header
  document.getElementById('clientName').textContent = data.client_name || 'Unknown Client';

  // Summary Strip (use safe enums)
  const displaySentiment = safeEnum(report.sentiment, allowedSentiments, 'Unknown');
  document.getElementById('sentimentValue').textContent = displaySentiment;
  const displayStage = safeEnum(report.lead_stage, allowedStages, 'Qualified');
  document.getElementById('stageValue').textContent = displayStage;
  document.getElementById('acceptanceValue').textContent = `${report.acceptance_probability || 0}%`;
  document.getElementById('urgencyValue').textContent = report.urgency_level || 'Medium';
  document.getElementById('confidenceValue').textContent = `${report.confidence_score || 0}%`;

  // Sentiment & Tone classes
  const sentimentMap = {
    'Positive': 'positive',
    'Cautiously Optimistic': 'positive',
    'Neutral': 'neutral',
    'Cautiously Pessimistic': 'mixed',
    'Negative': 'negative'
  };
  const sentimentClass = sentimentMap[displaySentiment] || 'neutral';
  const sentimentBadge = document.getElementById('sentimentBadge');
  sentimentBadge.textContent = displaySentiment;
  sentimentBadge.className = `sentiment-indicator ${sentimentClass}`;

  // Sentiment drivers (evidence-based)
  const drivers = Array.isArray(report.sentiment_drivers) ? report.sentiment_drivers : [];
  const driversList = document.getElementById('sentimentDriversList');
  if (drivers.length > 0) {
    driversList.innerHTML = drivers.map(d => `<li>${escapeHtml(d)}</li>`).join('');
  } else {
    driversList.innerHTML = '<li style="color:var(--muted)">No direct drivers cited</li>';
  }

  document.getElementById('emotionalTone').textContent = report.emotional_tone || 'Neutral';
  document.getElementById('hesitationLevel').textContent = report.objections?.length > 2 ? 'High' : 'Low';

  // Lead Stage Assessment
  const stageBadge = document.getElementById('stageBadge');
  stageBadge.textContent = displayStage;
  stageBadge.className = `stage-tag mini stage-${displayStage.toLowerCase().replace(/\s+/g,'-')}`;

  // Stage signals and blockers with evidence and confidence
  const stageSignals = Array.isArray(report.stage_signals) ? report.stage_signals : [];
  const stageSignalsList = document.getElementById('stageSignalsList');
  if (stageSignals.length > 0) {
    stageSignalsList.innerHTML = stageSignals.map(s => `<li>${escapeHtml(s)}</li>`).join('');
  } else {
    stageSignalsList.innerHTML = '<li style="color:var(--muted)">No explicit stage signals in transcript</li>';
  }

  const stageBlockers = Array.isArray(report.stage_blockers) ? report.stage_blockers : [];
  const stageBlockersList = document.getElementById('stageBlockersList');
  if (stageBlockers.length > 0) {
    stageBlockersList.innerHTML = stageBlockers.map(b => `<li>${escapeHtml(b)}</li>`).join('');
  } else {
    stageBlockersList.innerHTML = '<li>None identified</li>';
  }

  document.getElementById('stageConfidence').innerHTML = `${report.stage_confidence || 0}% ${formatConfidenceBadge(report.stage_confidence)}`;
  document.getElementById('advancementTimeline').textContent = report.advancement_timeline || 'Unknown';

  // Deal Probability Meter
  const prob = report.acceptance_probability || 0;
  const probabilityBar = document.getElementById('probabilityBar');
  const probClass = prob >= 75 ? 'high' : prob >= 45 ? 'medium' : 'low';
  probabilityBar.className = `progress-bar-fill ${probClass}`;
  probabilityBar.style.width = `${prob}%`;

  const probLabel = prob >= 75 ? 'High Probability' : prob >= 45 ? 'Medium Probability' : 'Low Probability';
  document.getElementById('probabilityLabel').textContent = probLabel;
  document.getElementById('probabilityScore').textContent = `${prob}%`;
  document.getElementById('dealConfidence').textContent = `${report.confidence_score || 0}%`;
  document.getElementById('fallbackFlag').textContent = report.is_fallback ? 'Yes ⚠️' : 'No';

  // Buying Signals (evidence-based rendering)
  const signals = Array.isArray(report.buying_signals) ? report.buying_signals : [];
  const signalsContainer = document.getElementById('buyingSignalsContainer');
  if (signals.length > 0) {
    signalsContainer.innerHTML = signals.map(s => {
      const obj = (typeof s === 'string') ? { signal: s } : s || {};
      const text = obj.signal || 'Unknown signal';
      const strength = safeEnum(obj.strength, allowedStrengths, 'Moderate');
      const category = safeEnum(obj.category, Object.keys({}), obj.category) || (obj.category || 'Other');
      const evidenceHtml = renderEvidence(obj.verbatim_evidence || obj.evidence);
      const confHtml = obj.confidence ? ` ${formatConfidenceBadge(obj.confidence)}` : '';
      const strengthColor = strength === 'Strong' ? 'var(--success)' : strength === 'Weak' ? 'var(--warning)' : 'var(--accent)';
      return `<div class="signal-card" style="border-left: 3px solid ${strengthColor}; padding:8px;">
                <div class="signal-main"><strong>${escapeHtml(text)}</strong> <small style="color:var(--muted);">${escapeHtml(category)}</small>${confHtml}</div>
                ${evidenceHtml}
              </div>`;
    }).join('');
  } else {
    signalsContainer.innerHTML = '<span style="color: var(--muted); font-size: 13px;">No buying signals detected</span>';
  }

  // Pain Points
  const painPoints = Array.isArray(report.pain_points) ? report.pain_points : [];
  const painPointsList = document.getElementById('painPointsList');
  if (painPoints.length > 0) {
    painPointsList.innerHTML = painPoints.map(p => `<li>${escapeHtml(p)}</li>`).join('');
  } else {
    painPointsList.innerHTML = '<li style="color:var(--muted)">No pain points explicitly mentioned</li>';
  }

  // Objections (evidence + severity)
  const objections = Array.isArray(report.objections) ? report.objections : [];
  const objectionsContainer = document.getElementById('objectionsContainer');
  if (objections.length > 0) {
    objectionsContainer.innerHTML = objections.map(o => {
      const obj = (typeof o === 'string') ? { objection: o, category: 'Other', severity: 'Medium' } : o || {};
      const text = obj.objection || 'Unknown objection';
      const category = safeEnum(obj.category, allowedObjectionCategories, 'Other');
      const severity = obj.severity || 'Medium';
      const evidenceHtml = renderEvidence(obj.verbatim_evidence || obj.evidence);
      const severityHtml = `<span class="severity-tag severity-${severity.toLowerCase()}">${escapeHtml(severity)}</span>`;
      const confHtml = obj.confidence ? ` ${formatConfidenceBadge(obj.confidence)}` : '';
      return `<div class="objection-card" style="padding:8px; border-radius:4px; border:1px solid var(--muted);">
                <div><strong>${escapeHtml(category)}</strong> ${severityHtml}${confHtml}</div>
                <div style="margin-top:6px;">${escapeHtml(text)}</div>
                ${evidenceHtml}
              </div>`;
    }).join('');
  } else {
    objectionsContainer.innerHTML = '<span style="color: var(--muted); font-size: 13px;">No objections identified</span>';
  }

  // Risks
  const risks = Array.isArray(report.risks) ? report.risks : [];
  const risksList = document.getElementById('risksList');
  if (risks.length > 0) {
    risksList.innerHTML = risks.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  } else {
    risksList.innerHTML = '<li>No risks identified</li>';
  }

  // Opportunities
  const opportunities = Array.isArray(report.opportunities) ? report.opportunities : [];
  const opportunitiesList = document.getElementById('opportunitiesList');
  if (opportunities.length > 0) {
    opportunitiesList.innerHTML = opportunities.map(o => `<li>${escapeHtml(o)}</li>`).join('');
  } else {
    opportunitiesList.innerHTML = '<li style="color: var(--muted);">No opportunities identified</li>';
  }

  // Stakeholders (render verbatim only; do not infer titles)
  const stakeholders = Array.isArray(report.stakeholders) ? report.stakeholders : [];
  const stakeholdersList = document.getElementById('stakeholdersList');
  if (stakeholders.length > 0) {
    stakeholdersList.innerHTML = stakeholders.map(s => `<div class="stakeholder-tag">${escapeHtml(s)}</div>`).join('');
  } else {
    stakeholdersList.innerHTML = '<span style="color: var(--muted); font-size: 13px;">No stakeholders identified</span>';
  }

  // Quotes (verbatim)
  const quotes = Array.isArray(report.client_quotes) ? report.client_quotes : [];
  const quotesContainer = document.getElementById('quotesContainer');
  if (quotes.length > 0) {
    quotesContainer.innerHTML = quotes.map(q => 
      `<blockquote style="margin: 0; padding-left: 12px; border-left: 3px solid var(--accent); font-size: 13px; font-style: italic; line-height: 1.5;">"${escapeHtml(q)}"</blockquote>`
    ).join('');
  } else {
    quotesContainer.innerHTML = '<span style="color: var(--muted);">No quotes available</span>';
  }

  // Sales Strategy
  document.getElementById('strategySummary').textContent = report.sales_strategy || 'Establish trust and gather more information';

  // Communication Style
  document.getElementById('communicationStyle').textContent = report.communication_style || 'Consultative and analytical';

  // Next Steps
  const nextSteps = Array.isArray(report.next_steps) ? report.next_steps : [];
  const nextStepsList = document.getElementById('nextStepsList');
  if (nextSteps.length > 0) {
    nextStepsList.innerHTML = nextSteps.map(s => `<li>${escapeHtml(s)}</li>`).join('');
  } else {
    nextStepsList.innerHTML = '<li style="color:var(--muted)">No next steps provided</li>';
  }

  // Recommendations
  const recommendations = Array.isArray(report.recommendations) ? report.recommendations : [];
  const recommendationsList = document.getElementById('recommendationsList');
  if (recommendations.length > 0) {
    recommendationsList.innerHTML = recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join('');
  } else {
    recommendationsList.innerHTML = '<li style="color:var(--muted)">No recommendations provided</li>';
  }

  // Follow-up Template
  document.getElementById('followUpTemplate').textContent = report.follow_up_strategy || 'Follow up with discovery questions to understand client needs better.';

  // Meeting Details
  document.getElementById('salesSpeaker').textContent = report.sales_speaker || 'Unknown';
  document.getElementById('clientSpeaker').textContent = report.client_speaker || 'Unknown';
  document.getElementById('meetingSummary').textContent = (report.summary || 'Analysis complete').substring(0, 150) + '...';

  // Executive Summary
  document.getElementById('executiveSummary').textContent = report.summary || 'Loading...';
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), 3000);
}

// Copy to Clipboard
document.getElementById('copyTemplateBtn')?.addEventListener('click', function() {
  const template = document.getElementById('followUpTemplate').textContent;
  navigator.clipboard.writeText(template).then(() => {
    showToast('Follow-up template copied to clipboard!');
  });
});

// Export Analysis
document.getElementById('exportBtn')?.addEventListener('click', function() {
  const clientName = document.getElementById('clientName').textContent;
  const summaryText = document.getElementById('executiveSummary').textContent;
  const exportData = {
    clientName,
    summary: summaryText,
    sentiment: document.getElementById('sentimentValue').textContent,
    stage: document.getElementById('stageValue').textContent,
    acceptance: document.getElementById('acceptanceValue').textContent,
    exportedAt: new Date().toISOString()
  };

  const csv = 'data:text/csv;charset=utf-8,' + encodeURIComponent(JSON.stringify(exportData, null, 2));
  const link = document.createElement('a');
  link.setAttribute('href', csv);
  link.setAttribute('download', `analysis_${clientName}_${Date.now()}.json`);
  link.click();
  showToast('Analysis exported!');
});

// Load on page load
document.addEventListener('DOMContentLoaded', loadMeetingAnalysis);
