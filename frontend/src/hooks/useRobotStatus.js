import { useState, useEffect, useRef } from 'react'

const POLL_INTERVAL_MS = 5000

export function useRobotStatus(robotId = 'R001') {
    const [status, setStatus] = useState(null)
    const [loading, setLoading] = useState(true)
    const timerRef = useRef(null)

    useEffect(() => {
        const apiUrl = import.meta.env.VITE_API_URL

        const fetch_status = () => {
            fetch(`${apiUrl}/planner/status?robot_id=${robotId}`)
                .then(res => res.ok ? res.json() : null)
                .then(data => {
                    if (data) setStatus(data)
                    setLoading(false)
                })
                .catch(() => setLoading(false))
        }

        fetch_status()
        timerRef.current = setInterval(fetch_status, POLL_INTERVAL_MS)

        return () => clearInterval(timerRef.current)
    }, [robotId])

    const isIdle = status ? status.pending_count === 0 : null

    return { status, loading, isIdle }
}
