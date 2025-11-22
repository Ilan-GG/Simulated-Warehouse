using UnityEngine;
using UnityEngine.AI;
using System.Collections.Generic;

public class BlindRobotScript : MonoBehaviour
{
    public string targetTag = "Box";
    public string shelfTag = "Shelf";

    public Transform grabPoint;
    public float grabDistance = 2.0f;

    private NavMeshAgent agent;

    private GameObject currBox;
    private ShelfScript currShelf;
    private Transform currShelfSpot;

    private bool hasBox = false;
    // private bool hasFinished = false;

    private List<GameObject> knownBoxes = new List<GameObject>();

    private enum BotState { Wander, GoingToKnownBox, Delivering }
    private BotState state = BotState.Wander;


    void Start()
    {
        agent = GetComponent<NavMeshAgent>();
        FindClosestBox();
    }

    void Update()
    {

        switch (state)
        {
            case BotState.Wander:
                Wander();
                break;

            case BotState.GoingToKnownBox:
                if (currBox == null)
                {
                    FindClosestBox();
                    return;
                }
                agent.SetDestination(currBox.transform.position);
                break;

            case BotState.Delivering:
                if (currShelf == null)
                {
                    FindClosestShelf();
                    return;
                }

                agent.SetDestination(currShelf.transform.position);
                break;
        }
    }

    void Wander()
    {
        if (!agent.hasPath || agent.remainingDistance < 0.5f)
        {
            Vector3 randomDir = Random.insideUnitSphere * 10f;
            randomDir.y = 0;

            Vector3 randomPos = transform.position + randomDir;

            agent.SetDestination(randomPos);
        }
    }
    
    void FindClosestBox()
    {
        float minDist = Mathf.Infinity;
        GameObject nearest = null;

        foreach (GameObject b in knownBoxes)
        {
            BoxScript bs = b.GetComponent<BoxScript>();

            // Filtros
            if (bs != null && (bs.isStored || bs.isAssigned))
                continue;

            float dist = Vector3.Distance(transform.position, b.transform.position);
            if (dist < minDist)
            {
                minDist = dist;
                nearest = b;
            }
        }

        currBox = nearest;

        if (currBox == null) {
            //Debug.Log("No boxes available (all are stored or Assigned).");
            // hasFinished = true;

            state = BotState.Wander;
        } else {
            BoxScript CurrBs = currBox.GetComponent<BoxScript>();
            CurrBs.isAssigned = true;
        }
    }


    void FindClosestShelf()
    {
        GameObject[] shelves = GameObject.FindGameObjectsWithTag(shelfTag);

        float minDist = Mathf.Infinity;
        ShelfScript nearestShelf = null;
        Transform nearestSpot = null;

        foreach (GameObject s in shelves)
        {
            ShelfScript sc = s.GetComponent<ShelfScript>();
            Transform freeSpot = sc.GetFirstFreeSpot();

            if (freeSpot != null) // Solo considerar si tiene espacio
            {
                float dist = Vector3.Distance(transform.position, freeSpot.position);
                if (dist < minDist)
                {
                    minDist = dist;
                    nearestShelf = sc;
                    nearestSpot = freeSpot;
                }
            }
        }

        currShelf = nearestShelf;
        // currShelfSpot = null; // El spot NO se calcula aquí

    }
    
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag(targetTag))
        {
            if (!knownBoxes.Contains(other.gameObject))
                knownBoxes.Add(other.gameObject);

            if (!hasBox)
            {
                BoxScript CurrBs = other.gameObject.GetComponent<BoxScript>();
                CurrBs.isAssigned = true;
                PickUpBox(other.gameObject);
            }
        }

    }

    void PickUpBox(GameObject box)
    {
        Debug.Log("Caja agarrada: " + box.name);

        // Desactivar física
        if (box.TryGetComponent<Rigidbody>(out Rigidbody rb))
        {
            rb.isKinematic = true;
        }

        // Mover al punto de agarre
        box.transform.SetParent(grabPoint);
        box.transform.localPosition = Vector3.zero;
        box.transform.localRotation = Quaternion.identity;

        hasBox = true;
        currBox = null;
        state = BotState.Delivering;
        //knownBoxes.Remove(box);
    }

    private void OnTriggerStay(Collider other)
    {
        if (!hasBox) return;
        // if (currShelfSpot == null) return;

        // Pseudo Collider
        Vector3 deliveryPoint = new Vector3(currShelf.transform.position.x, 0.5f, currShelf.transform.position.z);
        float dist = Vector3.Distance(transform.position, deliveryPoint);

        if (dist < 1.5f)
        {
            Debug.Log("Dejando Caja");
            DropBox();
        }
    }

    void DropBox()
    {
        if (currShelf != null)
            currShelfSpot = currShelf.GetFirstFreeSpot();

        if (currShelfSpot == null)
        {
            Debug.LogWarning("Ningún spot disponible al momento de dejar la caja. Rebuscando shelf...");
            hasBox = true;
            currShelf = null;
            FindClosestShelf();
            return;
        }

        Transform box = grabPoint.GetChild(0);

        // Marcar la caja como almacenada
        if (box.TryGetComponent<BoxScript>(out BoxScript bs))
            bs.isStored = true;

        // Colocar en shelf
        box.SetParent(currShelfSpot);
        box.localPosition = Vector3.zero;
        box.localRotation = Quaternion.identity;

        hasBox = false;
        currShelf = null;
        currShelfSpot = null;

        state = BotState.GoingToKnownBox;

        FindClosestBox();
    }


}
