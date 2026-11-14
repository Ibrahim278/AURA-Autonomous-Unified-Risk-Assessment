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
import ResearchPanel from './components/ResearchPanel.jsx'
import DemoTour, { TOUR_STEPS } from './components/DemoTour.jsx'

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
  const [askSignal, setAskSignal] = useState(0)
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
      const [s, t, a, r, f] = await Promise.all([
        api.status(crewId, day),
        api.telemetry(crewId),
        api.alerts(crewId),
        api.tasks(crewId),
        api.forecast(crewId, day),
      ])
      setForecast(f)
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

  const goToStep = useCallback((i) => {
    const st = TOUR_STEPS[i]
    if (!st) return
    setTourStep(i)
    setCrewId(st.crew)
    setDay(st.day)
    setSystem(null)
    setSelected(st.indicator)
    setTimeout(() => {
      document.querySelector(st.target)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 450)
  }, [])

  const refreshAll = useCallback(async () => {
    await Promise.all([loadMission(), loadCrew()])
  }, [loadMission, loadCrew])

  const startTour = useCallback(async () => {
        // The tour follows the demo crew's scripted scenarios, so restore them if the crew was edited.
        const demoReady = crew.some((c) => c.id === 'aura-2' && c.scenario === 'behavioural_cardio') &&
          crew.some((c) => c.id === 'aura-3' && c.scenario === 'immune_fever')
        if (!demoReady) {
          const o = await api.crewOptions()
          await api.setCrew({ crew: o.default_crew })
          await refreshAll()
        }
        goToStep(0)
      }, [crew, refreshAll, goToStep])

  const scrollTo = (sel) => setTimeout(() => {
    document.querySelector(sel)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 350)

  const handleAction = (a) => {
    switch (a.type) {
      case 'open_indicator': setSystem(null); setSelected(a.target); scrollTo('.detail'); break
      case 'select_crew': setCrewId(a.target); setSelected(null); setSystem(null); scrollTo('.banner'); break
      case 'open_checkin': setDay(null); scrollTo('#checkin'); break
      case 'open_briefing': scrollTo('.ai-panel'); break
      case 'open_crew_editor': setEditingCrew('edit'); break
      case 'open_import': setEditingCrew('import'); break
      case 'add_indicator': setManagingIndicators(true); break
      case 'open_research': scrollTo('#research'); break
      case 'start_tour': startTour(); break
      default: break
    }
  }

  const member = useMemo(() => crew.find((c) => c.id === crewId), [crew, crewId])
  const shownDay = day ?? mission?.current_day
  const selectedAssessment = status?.indicators.find((i) => i.indicator === selected)

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

  return (
    <div className="app">
      <Header mission={mission} onTour={startTour} onReset={async (env) => {
        await api.reset({ environment: env, days: mission?.days ?? 60 })
        setDay(null)
        setSelected(null)
        await refreshAll()
      }} />
      <div className="layout">
        <aside className="sidebar">
          <CrewList crew={crew} selectedId={crewId} onEdit={() => setEditingCrew('edit')} onImport={() => setEditingCrew('import')} onSelect={(id) => {
            setCrewId(id)
            setSelected(null)
            setSystem(null)
          }} />
          {mission && (
            <DayScrubber
              currentDay={mission.current_day}
              day={shownDay}
              live={day === null}
              onChange={(d) => setDay(d >= mission.current_day ? null : d)}
            />
          )}
          <div className="panel-lite">
            <MissionRoutine
              crewId={crewId}
              data={routine}
              onChange={setRoutine}
              onGoToCheckin={() => {
                setDay(null)
                document.getElementById('checkin')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
              }}
            />
          </div>
        </aside>

        <main className="main">
          {error && <div className="toast error">{error}</div>}
          {status && member && (
            <>
              <StatusBanner member={member} status={status} live={day === null} />
              <AIPanel
                key={`${crewId}-${shownDay}`}
                crewId={crewId}
                member={member}
                day={shownDay}
                live={day === null}
                catalog={catalog}
                onSelectIndicator={(k) => { setSystem(null); setSelected(k); scrollTo('.detail') }}
                forecast={forecast}
                onAsk={() => setAskSignal((n) => n + 1)}
              />
              <section className="overview">
                <div className="panel body-panel">
                  <h2>Body status</h2>
                  <BodyFigure
                    systems={status.body_systems}
                    selected={system}
                    onSelect={(s) => setSystem((prev) => (prev === s ? null : s))}
                  />
                </div>
                <div className="panel">
                  <IndicatorGrid
                    indicators={status.indicators}
                    telemetry={telemetry}
                    filterSystem={system}
                    onClearFilter={() => setSystem(null)}
                    selected={selected}
                    onSelect={setSelected}
                    day={shownDay}
                    onManage={() => setManagingIndicators(true)}
                  />
                </div>
              </section>

              {selectedAssessment && (
                <IndicatorDetail
                  assessment={selectedAssessment}
                  info={catalog[selected]}
                  series={telemetry?.series[selected]}
                  projection={forecast?.day === shownDay ? forecast?.series[selected] : null}
                  day={shownDay}
                  onClose={() => setSelected(null)}
                />
              )}

              <section className="bottom">
                <div className="panel" id="checkin">
                  <CheckInForm
                    crewId={crewId}
                    catalog={catalog}
                    disabled={day !== null}
                    onSaved={refreshAll}
                    day={mission?.current_day}
                    onNextDay={async () => {
                      const m = await api.nextDay()
                      setDay(null)
                      await refreshAll()
                      return m
                    }}
                  />
                </div>
                <div className="panel">
                  <AlertTimeline
                    alerts={alerts}
                    upToDay={shownDay}
                    onSelect={(key, d) => {
                      setSelected(key)
                      setDay(d >= mission.current_day ? null : d)
                    }}
                  />
                </div>
              </section>

              <ResearchPanel focus={tourStep !== null ? TOUR_STEPS[tourStep]?.research : null} />
            </>
          )}
        </main>
      </div>
      {managingIndicators && (
        <IndicatorManager
          catalog={catalog}
          onClose={() => setManagingIndicators(false)}
          onChanged={async (key) => {
            await refreshAll()
            setSystem(null)
            setSelected(key)
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
