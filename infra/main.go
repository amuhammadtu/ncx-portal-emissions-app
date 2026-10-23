// Package main provisions the SEAL Golden Path Cloud Run service, IAP perimeter,
// and least-privilege Service Account for the NCX Portal Emission Analytics app (ENG-2079).
package main

import (
	"github.com/pulumi/pulumi/sdk/v3/go/pulumi"
	"github.com/transurban/seal-platform-sdk/go/platform"
)

func main() {
	pulumi.Run(func(ctx *pulumi.Context) error {
		app, err := platform.NewStreamlitApp(ctx, "ncx-portal-emissions", &platform.StreamlitAppArgs{
			AppName:                pulumi.String("ncx-portal-emissions"),
			CostCentre:             pulumi.String("AM-VENTILATION-113"),
			DataSensitivity:        pulumi.String("internal-engineering"),
			Region:                 pulumi.String("australia-southeast1"),
			Ingress:                pulumi.String("INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"),
			VpcEgress:              pulumi.String("PRIVATE_RANGES_ONLY"),
			ExecutionEnvironment:   pulumi.String("EXECUTION_ENVIRONMENT_GEN2"),
			CpuIdle:                pulumi.Bool(false), // Mandatory for WebSocket & ADK streaming (ENG-2079)
			SessionAffinity:        pulumi.Bool(true),  // Mandatory for stateful Streamlit sessions (ENG-2079)
			Concurrency:            pulumi.Int(80),
			TimeoutSeconds:         pulumi.Int(3600),
			MinInstances:           pulumi.Int(0),
			MaxInstances:           pulumi.Int(5),
			EnableIap:              pulumi.Bool(true),
			WorkforceIdentityPool:  pulumi.String("locations/global/workforcePools/agentspace-entra-id-p-oidc-exnat"),
			AllowedEntraGroups:     pulumi.ToStringArray([]string{"grp-tu-am-ventilation-engineers", "grp-tu-ncx-operations"}),
			BigQueryProject:        pulumi.String("tu-data-edw-pr-1"),
			BigQueryDatasets:       pulumi.ToStringArray([]string{"a113_roadside"}),
			MaxBytesBilledPerQuery: pulumi.Int(5368709120), // 5 GiB circuit breaker (ENG-2083)
			RegisterAgentspaceCard: pulumi.Bool(true),      // Publishes .well-known/agent.json (ENG-2085)
		})
		if err != nil {
			return err
		}

		ctx.Export("serviceUrl", app.ServiceUrl)
		ctx.Export("serviceAccountEmail", app.ServiceAccountEmail)
		ctx.Export("iapAudience", app.IapAudience)
		return nil
	})
}
