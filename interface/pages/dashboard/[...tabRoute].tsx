import React, { useCallback, useEffect } from "react";
import { useRouter } from "next/router";

import Dashboard from "../../components/Dashboard";
import Community from "../../components/Community";
import CommunityList from "../../components/CommunityList";
import APIKeyList from "../../components/APIKeyList";

const TabRoute = (props: any) => {
  const router = useRouter();
  const [tab, id] = ([] as string[]).concat(router.query.tabRoute || []);

  const findComponent = useCallback(
    (tab: string, id?: string): React.ReactNode | void => {
      switch (tab) {
        case "community":
          return id ? <Community id={id} /> : <CommunityList />;
        case "api-keys":
          return <APIKeyList />;
      }
    },
    []
  );

  const component = findComponent(tab, id);

  useEffect(() => {
    if (tab && !component) router.push("/404");
  }, [router, component, tab]);

  return (
    // TODO - fix dashboard is being rendered twice
    <Dashboard {...props} activeTab={tab}>
      {component}
    </Dashboard>
  );
};

export default TabRoute;
