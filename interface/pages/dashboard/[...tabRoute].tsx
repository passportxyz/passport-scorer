import React, { useCallback, useContext, useEffect } from "react";
import { useRouter } from "next/router";

import Dashboard from "../../components/Dashboard";
import Community from "../../components/Community";
import CommunityList from "../../components/CommunityList";
import APIKeyList from "../../components/APIKeyList";
import { UserContext } from "../../context/userContext";

const TabRoute = (props: any) => {
  const router = useRouter();
  const [tab, id] = ([] as string[]).concat(router.query.tabRoute || []);

  const findComponent = useCallback(
    (tab: string, id?: string): React.ReactNode | void => {
      switch (tab) {
        case "scorer":
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

  const { connected } = useContext(UserContext);

  useEffect(() => {
    if (!connected) {
      router.push("/");
    }
  }, [connected]);

  return (
    // TODO - fix dashboard is being rendered twice
    <Dashboard {...props} activeTab={tab}>
      {component}
    </Dashboard>
  );
};

export default TabRoute;
