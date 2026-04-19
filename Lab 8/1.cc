/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */ 
 
#include "ns3/core-module.h" 
#include "ns3/network-module.h" 
#include "ns3/internet-module.h" 
#include "ns3/point-to-point-module.h" 
#include "ns3/applications-module.h" 
 
#include <fstream> 
 
using namespace ns3; 
 
NS_LOG_COMPONENT_DEFINE ("FirstTcpFinal"); 
 
/* Congestion Window Trace Callback */ 
static void 
CwndChange (uint32_t oldCwnd, uint32_t newCwnd) 
{ 
  static std::ofstream out ("first_cwnd.tr"); 
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
  // Set TCP NewReno (ns-3.27 compatible) 
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", 
                      TypeIdValue (TypeId::LookupByName ("ns3::TcpNewReno"))); 
 
  NodeContainer nodes; 
  nodes.Create (2); 
 
  PointToPointHelper p2p; 
  p2p.SetDeviceAttribute ("DataRate", StringValue ("5Mbps")); 
  p2p.SetChannelAttribute ("Delay", StringValue ("2ms")); 
 
  NetDeviceContainer devices = p2p.Install (nodes); 
 
  InternetStackHelper stack; 
  stack.Install (nodes); 
 
  Ipv4AddressHelper address; 
  address.SetBase ("10.1.1.0", "255.255.255.0"); 
  Ipv4InterfaceContainer interfaces = address.Assign (devices); 
 
  uint16_t port = 8080; 
 
  // TCP Server 
  PacketSinkHelper sink ("ns3::TcpSocketFactory", 
                         InetSocketAddress (Ipv4Address::GetAny (), port)); 
  ApplicationContainer serverApps = sink.Install (nodes.Get (1)); 
  serverApps.Start (Seconds (0.0)); 
  serverApps.Stop (Seconds (20.0)); 
 
  // TCP Client 
  BulkSendHelper source ("ns3::TcpSocketFactory", 
                         InetSocketAddress (interfaces.GetAddress (1), port)); 
  source.SetAttribute ("MaxBytes", UintegerValue (5 * 1024 * 1024)); // 5 MB 
 
  ApplicationContainer clientApps = source.Install (nodes.Get (0)); 
  clientApps.Start (Seconds (1.0)); 
  clientApps.Stop (Seconds (20.0)); 
 
  Simulator::Schedule (Seconds (1.1), &TraceCwnd); 
 
  Simulator::Stop (Seconds (20.0)); 
  Simulator::Run (); 
  Simulator::Destroy (); 
  return 0; 
}
