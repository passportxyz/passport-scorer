import { useRouter } from 'next/router'

const Community = () => {
  const router = useRouter()
  const { id } = router.query

  return <p>Community: {id}</p>
}

export default Community