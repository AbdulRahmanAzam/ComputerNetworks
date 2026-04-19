/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */ 
/* 
* TCP Point-to-Point + CSMA Simulation with Congestion Window Tracing 
* ns-3.27 Compatible 
*/ 
#include "ns3/core-module.h" 
#include "ns3/network-module.h" 
#include "ns3/csma-module.h" 
#include "ns3/internet-module.h" 
#include "ns3/point-to-point-module.h" 
#include "ns3/applications-module.h" 
#include "ns3/ipv4-global-routing-helper.h" 
#include "ns3/netanim-module.h" 
#include <fstream> 
using namespace ns3; 
NS_LOG_COMPONENT_DEFINE ("SecondTcpFinal"); 
/* Congestion Window Trace Callback */ 
static void 
CwndChange (uint32_t oldCwnd, uint32_t newCwnd) 
{ 
static std::ofstream out ("second_cwnd.tr"); 
out << Simulator::Now ().GetSeconds () << " " << newCwnd << std::endl; 
} 
/* Attach trace AFTER socket creation (ns-3.27 safe) */ 
static void 
TraceCwnd () 
{ 
Config::ConnectWithoutContext ( 
"/NodeList/0/$ns3::TcpL4Protocol/SocketList/0/CongestionWindow", 
MakeCallback (&CwndChange)); 
} 
int main (int argc, char *argv[]) 
{ 
uint32_t nCsma = 3; 
  CommandLine cmd; 
  cmd.AddValue ("nCsma", "Number of CSMA nodes", nCsma); 
  cmd.Parse (argc, argv); 
 
  // Set TCP NewReno (ns-3.27 compatible) 
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", 
                      TypeIdValue (TypeId::LookupByName ("ns3::TcpNewReno"))); 
 
  NodeContainer p2pNodes; 
  p2pNodes.Create (2); 
 
  NodeContainer csmaNodes; 
  csmaNodes.Add (p2pNodes.Get (1)); 
  csmaNodes.Create (nCsma); 
 
  PointToPointHelper p2p; 
  p2p.SetDeviceAttribute ("DataRate", StringValue ("5Mbps")); 
  p2p.SetChannelAttribute ("Delay", StringValue ("2ms")); 
 
  NetDeviceContainer p2pDevices = p2p.Install (p2pNodes); 
 
  CsmaHelper csma; 
  csma.SetChannelAttribute ("DataRate", StringValue ("100Mbps")); 
  csma.SetChannelAttribute ("Delay", TimeValue (NanoSeconds (6560))); 
 
  NetDeviceContainer csmaDevices = csma.Install (csmaNodes); 
 
  InternetStackHelper stack; 
  stack.Install (p2pNodes.Get (0)); 
  stack.Install (csmaNodes); 
 
  Ipv4AddressHelper address; 
 
  address.SetBase ("10.1.1.0", "255.255.255.0"); 
  Ipv4InterfaceContainer p2pInterfaces = address.Assign (p2pDevices); 
 
  address.SetBase ("10.1.2.0", "255.255.255.0"); 
  Ipv4InterfaceContainer csmaInterfaces = address.Assign (csmaDevices); 
 
  uint16_t port = 9000; 
 
  // TCP Server 
  PacketSinkHelper sink ("ns3::TcpSocketFactory", 
                         InetSocketAddress (Ipv4Address::GetAny (), port)); 
  ApplicationContainer serverApps = sink.Install (csmaNodes.Get (nCsma)); 
  serverApps.Start (Seconds (0.0)); 
  serverApps.Stop (Seconds (20.0)); 
 
  // TCP Client (LIMITED DATA) 
  BulkSendHelper source ("ns3::TcpSocketFactory", 
                         InetSocketAddress (csmaInterfaces.GetAddress (nCsma), port)); 
  source.SetAttribute ("MaxBytes", UintegerValue (5 * 1024 * 1024)); // 5 MB 
 
  ApplicationContainer clientApps = source.Install (p2pNodes.Get (0)); 
  clientApps.Start (Seconds (1.0)); 
  clientApps.Stop (Seconds (20.0)); 
 
  Ipv4GlobalRoutingHelper::PopulateRoutingTables (); 
 
  
  Simulator::Schedule (Seconds (1.1), &TraceCwnd); 
 
  AnimationInterface anim ("second_tcp.xml"); 
 
  Simulator::Stop (Seconds (20.0)); 
 
  Simulator::Run (); 
  Simulator::Destroy (); 
  return 0; 
} 
