import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import Header from './components/Header.jsx'
import CrewList from './components/CrewList.jsx'
import StatusBanner from './components/StatusBanner.jsx'
import BodyFigure from './components/BodyFigure.jsx'
import IndicatorGrid from './components/IndicatorGrid.jsx'
import IndicatorDetail from './components/IndicatorDetail.jsx'
import CheckInForm from './components/CheckInForm.jsx'
import AlertTimeline from './components/AlertTimeline.jsx'
import DayScrubber from './components/DayScrubber.jsx'
import AIPanel from './components/AIPanel.jsx'
import MissionRoutine from './components/MissionRoutine.jsx'
import CrewEditor from './components/CrewEditor.jsx'
import IndicatorManager from './components/IndicatorManager.jsx'
import AssistantWidget from './components/AssistantWidget.jsx'
import CommsPanel from './components/CommsPanel.jsx'
import PlanPanel from './components/PlanPanel.jsx'
import TeamView from './components/TeamView.jsx'
import GroundView from './components/GroundView.jsx'
import SymptomLog from './components/SymptomLog.jsx'
import RadiationPanel from './components/RadiationPanel.jsx'
import ResearchPanel from './components/ResearchPanel.jsx'
import DemoTour, { TOUR_STEPS } from './components/DemoTour.jsx'
import Landing from './components/Landing.jsx'
import NavBar, { RelatedLinks } from './components/NavBar.jsx'
import { PAGES, PAGE_OF_TARGET, pageFromHash } from './pages.js'

export default function App() {
  const [mission, setMission] = useState(null)
  const [catalog, setCatalog] = useState({})
  const [crew, setCrew] = useState([])
  const [crewId, setCrewId] = useState(null)
  const [day, setDay] = useState(null) // null = live (current mission day)
  const [status, setStatus] = useState(null)
  const [telemetry, setTelemetry] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [routine, setRoutine] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [radiation, setRadiation] = useState(null)
  const [askSignal, setAskSignal] = useState(0)
  const [groundDraft, setGroundDraft] = useState(null)
  const [page, setPage] = useState(pageFromHash)
  const [planSignal, setPlanSignal] = useState(0)
  const [symptomPrefill, setSymptomPrefill] = useState(null)
  const [system, setSystem] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState(null)
  const [tourStep, setTourStep] = useState(null)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [editingCrew, setEditingCrew] = useState(false)
  const [managingIndicators, setManagingIndicators] = useState(false)

  const loadMission = useCallback(async () => {
    try {
      const [m, inds, c] = await Promise.all([api.mission(), api.indicators(), api.crew()])
      setMission(m)
      setCatalog(Object.fromEntries(inds.map((i) => [i.key, i])))
      setCrew(c)
      setCrewId((prev) => prev ?? c[0]?.id ?? null)
      setError(null)
    } catch (e) {
      setError(`Can't reach the AURA API (${e.message}). Is the back end running on port 8000?`)
    }
  }, [])

  const loadCrew = useCallback(async () => {
    if (!crewId) return
    try {
      const [s, t, a, r, f, rad] = await Promise.all([
        api.status(crewId, day),
        api.telemetry(crewId),
        api.alerts(crewId),
        api.tasks(crewId),
        api.forecast(crewId, day),
        api.radiation(crewId, day),
      ])
      setForecast(f)
      setRadiation(rad)
      setStatus(s)
      setTelemetry(t)
      setAlerts(a)
      setRoutine(r)
    } catch (e) {
      setError(e.message)
    }
  }, [crewId, day])

  useEffect(() => {
    loadMission()
  }, [loadMission])

  useEffect(() => {
    loadCrew()
  }, [loadCrew])

  // ---------------------------------------------------------------- pages (hash routes: #/plan)
  useEffect(() => {
    const onHash = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const navigate = useCallback((id, sel = null) => {
    if (!PAGES[id]) return
    if (window.location.hash !== `#/${id}`) window.history.pushState(null, '', `#/${id}`)
    setPage(id)
    if (sel) {
      // On phones the tour card covers the lower half, so put the target at the top instead.
      setTimeout(() => document.querySelector(sel)?.scrollIntoView({ behavior: 'smooth', block: window.innerWidth <= 600 ? 'start' : 'center' }), 450)
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [])
  // Open a page and, once it has rendered, scroll to an element on it.
  const goTo = (sel) => navigate(PAGE_OF_TARGET[sel] ?? page, sel)
  const openIndicator = (k) => { setSystem(null); setSelected(k); goTo('.detail') }
  const openCrew = (id, target = 'status') => { setCrewId(id); setSelected(null); setSystem(null); navigate(target) }

  const goToStep = useCallback((i) => {
    const st = TOUR_STEPS[i]
    if (!st) return
    setTourStep(i)
    setCrewId(st.crew)
    setDay(st.day)
    setSystem(null)
    setSelected(st.indicator)
    navigate(st.page ?? PAGE_OF_TARGET[st.target] ?? 'status', st.target)
  }, [navigate])

  const refreshAll = useCallback(async () => {
    await Promise.all([loadMission(), loadCrew()])
  }, [loadMission, loadCrew])

  const startTour = useCallback(async () => {
    // The tour follows the demo crew's scripted scenarios, so restore them if the crew was edited.
    const demoReady = crew.some((c) => c.id === 'aura-2' && c.scenario === 'behavioural_cardio') &&
      crew.some((c) => c.id === 'aura-3' && c.scenario === 'immune_fever')
    const adaptive = mission?.baseline_mode === 'adaptive'
    if (adaptive) await api.setBaselineMode('preflight') // the tour's numbers use preflight baselines
    if (!demoReady) {
      const o = await api.crewOptions()
      await api.setCrew({ crew: o.default_crew })
    }
    if (!demoReady || adaptive) await refreshAll()
    goToStep(0)
  }, [crew, mission, refreshAll, goToStep])

  const handleAction = (a) => {
    switch (a.type) {
      case 'open_page': navigate(a.target); break
      case 'open_indicator': openIndicator(a.target); break
      case 'select_crew': openCrew(a.target, PAGES[page]?.crew ? page : 'status'); break
      case 'open_checkin': setDay(null); goTo('#checkin'); break
      case 'open_briefing': goTo('.ai-panel'); break
      case 'open_crew_editor': setEditingCrew('edit'); break
      case 'open_import': setEditingCrew('import'); break
      case 'add_indicator': setManagingIndicators(true); break
      case 'open_research': navigate('research'); break
      case 'start_tour': startTour(); break
      case 'message_ground': navigate('comms'); break
      case 'open_radiation': navigate('radiation'); break
      case 'open_plan': navigate('plan'); break
      case 'go_to_day': { const d = Number(a.target); setDay(d >= (mission?.current_day ?? 0) ? null : d); if (!PAGES[page]?.crew) navigate('status'); break }
      case 'draft_ground_message': setDay(null); setGroundDraft({ urgent: false, text: a.target, n: Date.now() }); navigate('comms'); break
      case 'log_symptom': setDay(null); setSymptomPrefill({ key: a.target, n: Date.now() }); goTo('#symptoms'); break
      case 'open_team': navigate('team'); break
      case 'open_ground': navigate('ground'); break
      case 'open_symptoms': setDay(null); goTo('#symptoms'); break
      default: break
    }
  }

  const member = useMemo(() => crew.find((c) => c.id === crewId), [crew, crewId])
  const shownDay = day ?? mission?.current_day
  const selectedAssessment = status?.indicators.find((i) => i.indicator === selected)
  const messageGround = (text) => { setGroundDraft({ urgent: true, text, n: Date.now() }); setDay(null); navigate('comms') }

  if (error && !mission) {
    return (
      <div className="app">
        <div className="error-screen">
          <h1>AURA</h1>
          <p>{error}</p>
          <code>cd backend &amp;&amp; uvicorn aura.main:app --reload</code>
          <button onClick={loadMission}>Retry</button>
        </div>
      </div>
    )
  }

  const crewPage = PAGES[page]?.crew
  const ready = status && member
  const banner = ready && (
    <StatusBanner member={member} status={status} live={day === null} onMessageGround={() => {
      const flagged = status.indicators.filter((i) => i.level === 'critical').map((i) => `${i.name} ${i.value} ${i.unit}`)
      messageGround(`AURA flagged critical readings: ${flagged.join(', ')}. Requesting flight surgeon review.`)
    }} />
  )

  return (
    <div className="app">
      <Header mission={mission} onHome={() => navigate('home')} onTour={startTour} onReset={async (env) => {
        await api.reset({ environment: env, days: mission?.days ?? 60 })
        setDay(null)
        setSelected(null)
        await refreshAll()
      }} onRestart={async () => {
        // Put the demo back exactly as it ships: default crew, preflight baselines, lunar base, day 60.
        const o = await api.crewOptions()
        await api.setCrew({ crew: o.default_crew })
        if (mission?.baseline_mode === 'adaptive') await api.setBaselineMode('preflight')
        await api.reset({ environment: 'lunar_surface', days: 60 })
        setDay(null)
        setSelected(null)
        setCrewId('aura-1')
        await refreshAll()
      }} />
      <NavBar page={page} onNavigate={navigate} />
      {page === 'home' ? (
        <main className="main home-main">
          {error && <div className="toast error">{error}</div>}
          <Landing mission={mission} crew={crew} onNavigate={navigate} onOpenCrew={(id) => openCrew(id)}
            onTour={startTour} onAsk={() => setAskSignal((n) => n + 1)}
            onEditCrew={() => setEditingCrew('edit')} onImport={() => setEditingCrew('import')}
            onAddIndicator={() => setManagingIndicators(true)} />
        </main>
      ) : (
        <div className="layout">
          <aside className="sidebar">
            <CrewList crew={crew} selectedId={crewId} onEdit={() => setEditingCrew('edit')} onImport={() => setEditingCrew('import')}
              onSelect={(id) => openCrew(id, crewPage ? page : 'status')} />
            {mission && (
              <DayScrubber currentDay={mission.current_day} day={shownDay} live={day === null}
                onChange={(d) => setDay(d >= mission.current_day ? null : d)} />
            )}
          </aside>
          <main className="main">
            {error && <div className="toast error">{error}</div>}
            <div className="page-title">
              <h1><span aria-hidden="true">{PAGES[page].icon}</span> {PAGES[page].title}</h1>
              {crewPage && member && <span className="muted">{member.name} · day {shownDay}{day === null ? ' (live)' : ' (replay)'}</span>}
            </div>
            {crewPage && banner}

            {page === 'status' && ready && (
              <>
                <AIPanel key={`${crewId}-${shownDay}`} crewId={crewId} member={member} day={shownDay} live={day === null}
                  catalog={catalog} onSelectIndicator={openIndicator} forecast={forecast} onAsk={() => setAskSignal((n) => n + 1)} />
                <section className="overview">
                  <div className="panel body-panel">
                    <h2>Body status</h2>
                    <BodyFigure systems={status.body_systems} selected={system} onSelect={(s) => setSystem((prev) => (prev === s ? null : s))} />
                  </div>
                  <div className="panel">
                    <IndicatorGrid indicators={status.indicators} telemetry={telemetry} filterSystem={system}
                      onClearFilter={() => setSystem(null)} selected={selected} onSelect={setSelected} day={shownDay}
                      onManage={() => setManagingIndicators(true)} baselineMode={mission?.baseline_mode}
                      onBaselineMode={async (mode) => { await api.setBaselineMode(mode); await refreshAll() }} />
                  </div>
                </section>
                {selectedAssessment && (
                  <IndicatorDetail assessment={selectedAssessment} info={catalog[selected]} series={telemetry?.series[selected]}
                    projection={forecast?.day === shownDay ? forecast?.series[selected] : null}
                    related={forecast?.day === shownDay ? forecast?.related?.[selected] ?? [] : []}
                    onSelect={(k) => { setSystem(null); setSelected(k) }} day={shownDay} onClose={() => setSelected(null)} />
                )}
              </>
            )}

            {page === 'checkin' && ready && (
              <>
                <div className="panel" id="checkin">
                  <CheckInForm crewId={crewId} catalog={catalog} disabled={day !== null} onSaved={refreshAll}
                    onSymptoms={(keys) => { setSymptomPrefill({ keys, n: Date.now() }); goTo('#symptoms') }}
                    day={mission?.current_day}
                    onNextDay={async () => { const m = await api.nextDay(); setDay(null); await refreshAll(); return m }} />
                </div>
                <SymptomLog onLogged={() => setPlanSignal((n) => n + 1)} prefill={symptomPrefill} key={crewId} crewId={crewId}
                  day={shownDay} live={day === null} catalog={catalog} onOpenIndicator={openIndicator}
                  onMessageGround={(t) => messageGround(`Symptom triage is critical: ${t.reasons.join(' ')} Requesting flight surgeon review.`)} />
              </>
            )}

            {page === 'plan' && ready && (
              <PlanPanel crewId={crewId} day={shownDay} live={day === null} catalog={catalog} onOpenIndicator={openIndicator}
                refreshKey={`${status.overall}-${status.counts.warning}-${status.counts.critical}-${planSignal}`} />
            )}

            {page === 'radiation' && ready && <RadiationPanel budget={radiation} onOpenIndicator={openIndicator} />}

            {page === 'comms' && member && (
              <div className="panel comms-page">
                <CommsPanel key={`${crewId}-${mission?.environment}-${mission?.current_day}`} crewId={crewId} member={member}
                  live={day === null} prefill={groundDraft} />
              </div>
            )}

            {page === 'timeline' && ready && (
              <div className="panel">
                <AlertTimeline alerts={alerts} catalog={catalog} upToDay={shownDay}
                  onSelect={(key, d) => { setDay(d >= mission.current_day ? null : d); openIndicator(key) }} />
              </div>
            )}

            {page === 'routine' && member && (
              <div className="panel routine-page">
                <MissionRoutine crewId={crewId} data={routine} onChange={setRoutine}
                  onGoToCheckin={() => { setDay(null); goTo('#checkin') }} />
              </div>
            )}

            {page === 'team' && mission && (
              <TeamView day={shownDay} live={day === null} refreshKey={mission.current_day} onOpenCrew={(id) => openCrew(id)} />
            )}
            {page === 'ground' && mission && (
              <GroundView day={shownDay} live={day === null} refreshKey={mission.current_day} onOpenCrew={(id) => openCrew(id)} />
            )}
            {page === 'research' && (
              <ResearchPanel focus={tourStep !== null ? TOUR_STEPS[tourStep]?.research : null} />
            )}

            <RelatedLinks page={page} onNavigate={navigate} />
          </main>
        </div>
      )}
      {managingIndicators && (
        <IndicatorManager
          catalog={catalog}
          onClose={() => setManagingIndicators(false)}
          onChanged={async (key) => {
            await refreshAll()
            setSystem(null)
            setSelected(key)
            navigate('status', '.detail')
          }}
        />
      )}
      {editingCrew && (
        <CrewEditor
          crew={crew}
          onClose={() => setEditingCrew(false)}
          startImport={editingCrew === 'import'}
          customKeys={Object.values(catalog).filter((i) => i.custom).map((i) => i.key)}
          onSaved={async (saved, focusId) => {
            setDay(null)
            setSelected(null)
            setSystem(null)
            setCrewId((prev) => focusId ?? (saved.some((c) => c.id === prev) ? prev : saved[0]?.id ?? null))
            await refreshAll()
            if (page === 'home') navigate('status')
          }}
        />
      )}
      {tourStep !== null && !assistantOpen && (
        <DemoTour step={tourStep} onStep={goToStep} onClose={() => { setTourStep(null); setDay(null) }} />
      )}
      <AssistantWidget
        crewId={crewId}
        member={member}
        day={shownDay}
        live={day === null}
        selected={selected}
        selectedName={selected ? catalog[selected]?.name : null}
        page={page}
        onOpenChange={setAssistantOpen}
        highlight={tourStep !== null && TOUR_STEPS[tourStep]?.highlight === 'assistant'}
        openSignal={askSignal}
        onAction={handleAction}
      />
      <footer className="footer">
        Prototype: thresholds are research-informed prototype rules, not clinically validated
        flight-medicine limits. Demo telemetry is synthetic; the Inspiration4 panel shows real NASA OSDR data.
      </footer>
    </div>
  )
}
